import json
import os
from functools import lru_cache
import boto3


@lru_cache
def load():
    if os.getenv("SLACK_SECRET_ARN"):
        value = boto3.client("secretsmanager").get_secret_value(
            SecretId=os.environ["SLACK_SECRET_ARN"]
        )
        secret = json.loads(value["SecretString"])
        for key in ("SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET"):
            os.environ[key] = secret[key]
