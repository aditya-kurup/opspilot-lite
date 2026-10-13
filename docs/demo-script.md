# OpsPilot Lite Recording Script

## Before recording

Start the local simulator:

```bash
.venv/bin/python -m app.demo
```

Open `http://127.0.0.1:8000`, click the reset icon in the top right, and keep the browser at a desktop width where the request composer and approval queue are visible together. This recording uses the mock parser and `DRY_RUN=true`; no AWS resource is created.

## Three-minute flow

**0:00 - Context**

"OpsPilot Lite turns a natural language infrastructure request into a constrained plan. The model can propose an action, but it cannot execute AWS. A separate authorized user must approve it."

**0:20 - Submit a valid request**

Use the prefilled request:

`Create a dev bucket named campus-demo for 2 hours`

Click **Send for approval**. Point out the pending request, the supported action, and the 72-hour maximum.

**0:50 - Demonstrate self-approval protection**

Choose **Alex - Requester** in the identity selector and click **Approve plan**. Show the refusal message. Explain that the requester cannot approve their own request.

**1:15 - Demonstrate authorized approval**

Choose **Morgan - Authorized approver** and approve the request. Show the dry-run bucket name, expiry time, and audit entries for pending, executing, and provisioned states.

**1:50 - Demonstrate validation**

Choose the **Invalid request** example and submit it. Show that production or an excessive TTL is rejected before the approval queue.

**2:10 - Show audit and guardrails**

Open **Audit log** and **Guardrails**. Mention strict Pydantic validation, allowlisted actions, encryption and public-access blocking in the real executor, ownership tags, and empty-bucket-only cleanup.

**2:40 - Close accurately**

"The repository contains the same workflow wired for Slack Bolt, Lambda, SQS, DynamoDB, Bedrock, and CDK. This recording shows the safe local dry-run path; a deployed AWS demo would use the same approval state machine with real credentials and explicit deployment verification."

## Optional live Slack recording

Only use this section after testing a Slack workspace. Keep `DRY_RUN=true` for the first run. Do not show tokens, account IDs, or private workspace information on screen.
