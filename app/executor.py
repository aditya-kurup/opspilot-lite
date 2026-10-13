import os
from decimal import Decimal
from datetime import datetime, timedelta, timezone
import boto3
from botocore.exceptions import ClientError
from app.config import dry_run
from app.parser import ProvisionRequest


def bucket_name(name: str, request_id: str) -> str:
    return f"opspilot-{name}-{request_id[:12]}"


def create_bucket(item: dict, s3=None) -> dict:
    # DynamoDB represents numbers as Decimal; normalize before strict validation.
    normalized = dict(item)
    if isinstance(normalized.get("ttl_hours"), Decimal):
        normalized["ttl_hours"] = int(normalized["ttl_hours"])
    params = ProvisionRequest.model_validate(
        {key: normalized[key] for key in ("action", "name", "ttl_hours", "env")}
    )
    item = {**normalized, **params.model_dump()}
    bucket = bucket_name(item["name"], item["request_id"])
    expiry = (datetime.now(timezone.utc) + timedelta(hours=int(item["ttl_hours"]))).isoformat()
    if dry_run():
        return {"bucket": bucket, "ttl_expiry": expiry, "dry_run": True}
    s3 = s3 or boto3.client("s3")
    region = os.getenv("AWS_REGION", "us-east-1")
    args = {"Bucket": bucket}
    if region != "us-east-1":
        args["CreateBucketConfiguration"] = {"LocationConstraint": region}
    s3.create_bucket(**args)
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        s3.put_bucket_encryption(
            Bucket=bucket,
            ServerSideEncryptionConfiguration={
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
            },
        )
        s3.put_bucket_tagging(
            Bucket=bucket,
            Tagging={
                "TagSet": [
                    {"Key": key, "Value": str(value)}
                    for key, value in {
                        "owner": item["requester"],
                        "ttl_expiry": expiry,
                        "env": item["env"],
                        "managed_by": "opspilot",
                        "request_id": item["request_id"],
                    }.items()
                ]
            },
        )
    except Exception:
        # A partially configured bucket must never be presented as successfully provisioned.
        try:
            s3.delete_bucket(Bucket=bucket)
        except ClientError:
            pass
        raise
    return {"bucket": bucket, "ttl_expiry": expiry, "dry_run": False}


def delete_empty_bucket(bucket: str, s3=None, *, expired_at=None, request_id=None) -> str:
    if not bucket.startswith("opspilot-"):
        raise ValueError("bucket outside OpsPilot prefix")
    if dry_run():
        return "dry_run"
    s3 = s3 or boto3.client("s3")
    tags = {
        entry["Key"]: entry["Value"] for entry in s3.get_bucket_tagging(Bucket=bucket)["TagSet"]
    }
    if tags.get("managed_by") != "opspilot":
        raise ValueError("bucket is not managed by OpsPilot")
    if request_id and tags.get("request_id") != request_id:
        raise ValueError("resource does not match request")
    if expired_at and datetime.fromisoformat(tags["ttl_expiry"]) > expired_at:
        raise ValueError("resource tag has not expired")
    s3.delete_bucket(Bucket=bucket)  # Deliberately fails for nonempty buckets.
    return "deleted"
