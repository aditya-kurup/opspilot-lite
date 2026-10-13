# Why the LLM cannot touch AWS

The model is an untrusted text-to-data adapter. It receives redacted text and returns action, name, ttl_hours, and env. Pydantic rejects extra fields, unsupported actions, production environments, and durations outside one to 72 hours. The executor validates again before constructing fixed boto3 calls. No output is evaluated as Python, interpolated into shell code, or used as an IAM policy.

The parser Lambda has Bedrock access and no S3 mutation permission. The executor has prefix-scoped S3 permissions and no Bedrock access. Slack ingress authenticates signed requests and enqueues work; workers perform the slower operations. Only an explicitly configured approver who is different from the requester can approve or reject. Conditional database updates allow one worker to claim execution, even under duplicate clicks.

Generated bucket names include a UUID suffix. Encryption, all four public-access-block settings, and ownership/expiry tags are mandatory. A provisioning configuration failure triggers compensating deletion and a failed result. Cleanup checks the database expiry and resource tags, including request ownership, before attempting empty-bucket deletion. Nonempty buckets require manual handling; granting object deletion would exceed this MVP's cleanup policy.

The browser simulator demonstrates these decisions through the same Python services, with local SQLite and a deterministic parser. It forces dry-run execution and exposes selectable demo identities. It has no production authentication and is deliberately bound to localhost. Public hosting will use a separate, safe simulation deployment; live provisioning remains behind authenticated Slack.

This is an educational MVP. State/audit updates are separate writes, and external AWS effects cannot be transacted together with DynamoDB. A worker crash after claiming work can require manual reconciliation. Prefix IAM restrictions and explicit tag checks protect the intended scope, but a real organizational deployment would add transactional audit writes, operational alarms, request expiry, approval revocation, reconciliation, and per-user quotas.
