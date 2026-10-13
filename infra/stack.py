from pathlib import Path
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_lambda_event_sources as sources,
    aws_secretsmanager as secrets,
    aws_sqs as sqs,
)
from constructs import Construct


class OpsPilotStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        secret_arn = self.node.try_get_context("slack_secret_arn")
        approvers = self.node.try_get_context("approver_user_ids")
        if not secret_arn or not approvers:
            raise ValueError("Set CDK context slack_secret_arn and approver_user_ids")
        secret = secrets.Secret.from_secret_complete_arn(self, "SlackSecret", secret_arn)
        requests = dynamodb.Table(
            self,
            "Requests",
            partition_key=dynamodb.Attribute(name="request_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )
        requests.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(name="status", type=dynamodb.AttributeType.STRING),
        )
        audit = dynamodb.Table(
            self,
            "Audit",
            partition_key=dynamodb.Attribute(name="request_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="timestamp", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )
        parse_dlq = sqs.Queue(self, "ParseDeadLetters", retention_period=Duration.days(14))
        execute_dlq = sqs.Queue(self, "ExecuteDeadLetters", retention_period=Duration.days(14))
        parse_queue = sqs.Queue(
            self,
            "ParseQueue",
            visibility_timeout=Duration.minutes(6),
            dead_letter_queue=sqs.DeadLetterQueue(queue=parse_dlq, max_receive_count=3),
        )
        execute_queue = sqs.Queue(
            self,
            "ExecuteQueue",
            visibility_timeout=Duration.minutes(6),
            dead_letter_queue=sqs.DeadLetterQueue(queue=execute_dlq, max_receive_count=3),
        )
        root = Path(__file__).resolve().parent.parent
        package = root / "build" / "lambda"
        if not package.exists():
            raise ValueError("Run python scripts/package_lambda.py before cdk synth")
        env = {
            "REQUESTS_TABLE": requests.table_name,
            "AUDIT_TABLE": audit.table_name,
            "APPROVER_USER_IDS": approvers,
            "DRY_RUN": str(self.node.try_get_context("dry_run") or "true"),
            "LLM_PROVIDER": "bedrock",
            "BEDROCK_MODEL_ID": self.node.try_get_context("bedrock_model_id")
            or "amazon.nova-lite-v1:0",
            "SLACK_SECRET_ARN": secret_arn,
        }

        def function(name, handler, environment):
            return lambda_.Function(
                self,
                name,
                runtime=lambda_.Runtime.PYTHON_3_11,
                handler=handler,
                code=lambda_.Code.from_asset(str(package)),
                timeout=Duration.seconds(60),
                memory_size=256,
                environment=environment,
            )

        ingress = function(
            "Ingress",
            "app.web.handler",
            {
                "SLACK_SECRET_ARN": secret_arn,
                "WORK_QUEUE_URL": parse_queue.queue_url,
                "EXECUTION_QUEUE_URL": execute_queue.queue_url,
            },
        )
        parser = function("Parser", "app.handlers.queue_handler", env)
        executor = function("Executor", "app.handlers.execution_handler", env)
        cleanup = function(
            "Cleanup",
            "app.cleanup.handler",
            {key: env[key] for key in ("REQUESTS_TABLE", "AUDIT_TABLE", "DRY_RUN")},
        )
        for fn in (ingress, parser, executor):
            secret.grant_read(fn)
        for fn in (parser, executor, cleanup):
            requests.grant_read_write_data(fn)
            audit.grant_write_data(fn)
        parse_queue.grant_send_messages(ingress)
        execute_queue.grant_send_messages(ingress)
        parser.add_event_source(
            sources.SqsEventSource(parse_queue, batch_size=1, report_batch_item_failures=True)
        )
        executor.add_event_source(
            sources.SqsEventSource(execute_queue, batch_size=1, report_batch_item_failures=True)
        )
        parser.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:{self.partition}:bedrock:{self.region}::foundation-model/{env['BEDROCK_MODEL_ID']}"
                ],
            )
        )
        buckets = f"arn:{self.partition}:s3:::opspilot-*"
        executor.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:CreateBucket",
                    "s3:PutBucketTagging",
                    "s3:PutEncryptionConfiguration",
                    "s3:PutBucketPublicAccessBlock",
                    "s3:DeleteBucket",
                ],
                resources=[buckets],
            )
        )
        cleanup.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetBucketTagging", "s3:DeleteBucket"], resources=[buckets]
            )
        )
        events.Rule(
            self,
            "HourlyCleanup",
            schedule=events.Schedule.rate(Duration.hours(1)),
            targets=[targets.LambdaFunction(cleanup)],
        )
        api = apigw.RestApi(
            self,
            "SlackApi",
            deploy_options=apigw.StageOptions(throttling_rate_limit=5, throttling_burst_limit=10),
        )
        api.root.add_resource("slack").add_method("POST", apigw.LambdaIntegration(ingress))
        CfnOutput(self, "SlackRequestUrl", value=api.url + "slack")
        CfnOutput(self, "RequestsTable", value=requests.table_name)
        CfnOutput(self, "AuditTable", value=audit.table_name)
