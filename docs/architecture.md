# Architecture

~~~mermaid
flowchart LR
  U[Slack user] -->|/provision| I[Ingress Lambda]
  I --> Q1[SQS parse queue]
  Q1 --> P[Parser Lambda]
  P --> D[(DynamoDB requests)]
  P --> S[Slack approval message]
  S -->|Approve or reject| I
  I --> Q2[SQS execution queue]
  Q2 --> E[Executor Lambda]
  E --> B[(Private encrypted S3)]
  E --> D
  E --> A[(DynamoDB audit)]
  T[EventBridge hourly] --> C[Cleanup Lambda]
  C --> B
  C --> D
  P --> L[Bedrock]
~~~

Four Lambda roles keep ingress, model inference, provisioning, and cleanup permissions separate. The local browser/Socket Mode adapters reuse the service code with SQLite instead of DynamoDB.
