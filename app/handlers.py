import json
import hashlib
import logging
import os
import uuid

import boto3
from pydantic import ValidationError
from slack_bolt import App

from app import audit, llm
from app.config import approvers
from app.executor import create_bucket
from app.parser import parse_request
from app.integrations import create_servicenow_record, trigger_jenkins

logger = logging.getLogger(__name__)


def approval_blocks(item: dict) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Provision request* from <@{item['requester']}>\nCreate S3 bucket *{item['name']}* in *{item['env']}* for *{item['ttl_hours']} hours*.\nExpires automatically if empty.",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": "approve_request",
                    "value": item["request_id"],
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "action_id": "reject_request",
                    "value": item["request_id"],
                },
            ],
        },
    ]


def enqueue(payload: dict) -> None:
    url = os.getenv("WORK_QUEUE_URL")
    if url:
        boto3.client("sqs").send_message(QueueUrl=url, MessageBody=json.dumps(payload))
    else:
        from threading import Thread

        Thread(target=process_request, args=(payload,), daemon=True).start()


def process_request(payload: dict, client=None) -> None:
    from slack_sdk import WebClient

    client = client or WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    request_id = payload["request_id"]
    requester = payload["requester"]
    channel = payload["channel"]
    existing = audit.get_request(request_id)
    if existing:
        if existing.get("status") == "pending" and not existing.get("notification_sent"):
            client.chat_postMessage(
                channel=existing["channel"],
                text=f"Approval requested for {existing['name']}",
                blocks=approval_blocks(existing),
            )
            audit.update_fields(request_id, "pending", notification_sent=True)
        return
    try:
        parsed = parse_request(payload["text"], llm.parse)
        item = {
            "request_id": request_id,
            "requester": requester,
            "channel": channel,
            "status": "pending",
            "notification_sent": False,
            **parsed.model_dump(),
        }
        audit.save_request(item)
        audit.record(request_id, requester, "create_s3_bucket", parsed.model_dump(), "pending")
        service_now_id = create_servicenow_record(item)
        if service_now_id:
            audit.update_fields(request_id, "pending", servicenow_id=service_now_id)
        client.chat_postMessage(
            channel=channel,
            text=f"Approval requested for {parsed.name}",
            blocks=approval_blocks(item),
        )
        audit.update_fields(request_id, "pending", notification_sent=True)
    except (ValueError, ValidationError, json.JSONDecodeError) as exc:
        client.chat_postEphemeral(
            channel=channel,
            user=requester,
            text="I could not validate that request. Try: /provision create a dev bucket named demo for 2 hours",
        )
        logger.info("Request %s rejected by validation: %s", request_id, type(exc).__name__)
    except Exception:
        logger.exception("Failed to process request %s", request_id)
        raise


def decide(request_id: str, actor: str, decision: str, client, channel: str) -> str:
    item = audit.get_request(request_id)
    if not item:
        return "Request not found."
    if item["channel"] != channel:
        return "Request channel does not match."
    if actor == item["requester"] or actor not in approvers():
        return "You are not authorized to approve or reject this request."
    if decision == "reject":
        if not audit.transition(request_id, "pending", "rejected", decided_by=actor):
            return "This request has already been handled."
        audit.record(request_id, actor, item["action"], item, "rejected")
        client.chat_postMessage(
            channel=channel, text=f"Request {request_id[:8]} rejected by <@{actor}>."
        )
        return "Request rejected."
    if decision != "approve":
        return "Invalid decision."
    if not audit.transition(request_id, "pending", "executing", decided_by=actor):
        return "This request has already been handled."
    audit.record(request_id, actor, item["action"], item, "executing")
    try:
        trigger_jenkins(request_id)
    except Exception:
        logger.exception("Jenkins trigger failed for %s", request_id)
    try:
        result = create_bucket(item)
    except Exception as exc:
        logger.exception("Provisioning failed for %s", request_id)
        audit.transition(request_id, "executing", "failed", error=type(exc).__name__)
        audit.record(request_id, actor, item["action"], item, "failed", type(exc).__name__)
        client.chat_postMessage(
            channel=channel,
            text=f"Provisioning failed for request {request_id[:8]}. Check application logs.",
        )
        return "Provisioning failed."
    audit.transition(request_id, "executing", "provisioned", **result)
    audit.record(request_id, actor, item["action"], item, "provisioned", json.dumps(result))
    label = "DRY RUN: would create" if result["dry_run"] else "Created"
    client.chat_postMessage(
        channel=channel,
        text=f"{label} bucket {result['bucket']} for <@{item['requester']}>. Expires {result['ttl_expiry']} (empty buckets only).",
    )
    return "Approved."


def dispatch_decision(body: dict) -> None:
    payload = {
        "request_id": body["actions"][0]["value"],
        "actor": body["user"]["id"],
        "channel": body["channel"]["id"],
        "decision": "approve" if body["actions"][0]["action_id"] == "approve_request" else "reject",
    }
    if os.getenv("EXECUTION_QUEUE_URL"):
        boto3.client("sqs").send_message(
            QueueUrl=os.environ["EXECUTION_QUEUE_URL"], MessageBody=json.dumps(payload)
        )
    else:
        from threading import Thread

        Thread(target=process_decision, args=(payload,), daemon=True).start()


def process_decision(payload: dict, client=None):
    from slack_sdk import WebClient

    client = client or WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    message = decide(
        payload["request_id"], payload["actor"], payload["decision"], client, payload["channel"]
    )
    client.chat_postEphemeral(channel=payload["channel"], user=payload["actor"], text=message)


def build_app() -> App:
    from app.secrets import load

    load()
    app = App(
        token=os.environ["SLACK_BOT_TOKEN"],
        signing_secret=os.environ["SLACK_SIGNING_SECRET"],
        process_before_response=bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME")),
        token_verification_enabled=False,
    )

    @app.command("/provision")
    def provision(ack, body):
        ack("Received. I’ll validate your request and post it for approval.")
        trigger_id = body.get("trigger_id")
        request_id = (
            hashlib.sha256(trigger_id.encode()).hexdigest()[:32]
            if trigger_id
            else str(uuid.uuid4())
        )
        enqueue(
            {
                "request_id": request_id,
                "requester": body["user_id"],
                "channel": body["channel_id"],
                "text": body.get("text", ""),
            }
        )

    @app.action("approve_request")
    def approve(ack, body):
        dispatch_decision(body)
        ack()

    @app.action("reject_request")
    def reject(ack, body):
        dispatch_decision(body)
        ack()

    return app


def queue_handler(event, context):
    from app.secrets import load

    load()
    from slack_sdk import WebClient

    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    failures = []
    for record in event["Records"]:
        try:
            process_request(json.loads(record["body"]), client)
        except Exception:
            logger.exception("Queue message failed")
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}


def execution_handler(event, context):
    from app.secrets import load

    load()
    failures = []
    for record in event["Records"]:
        try:
            process_decision(json.loads(record["body"]))
        except Exception:
            logger.exception("Execution message failed")
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
