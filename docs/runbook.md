# OpsPilot runbook

Create a Secrets Manager JSON secret containing SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET, package the Lambdas, and deploy with dry_run=true first. Configure the emitted API URL in Slack.

Set JENKINS_URL, JENKINS_JOB, and JENKINS_TOKEN to trigger the approval pipeline. Set SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASSWORD, and optionally SERVICENOW_TABLE to create request records. Store all credentials in secret stores.

Inspect CloudWatch logs and request/audit tables for incidents. Reconcile requests stuck in executing before retrying. Cleanup deletes only expired empty buckets.
