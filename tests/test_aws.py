from datetime import datetime, timedelta, timezone
import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
from app import audit, cleanup
from app.executor import create_bucket, delete_empty_bucket


def request():
    return {
        "request_id": "abc12345-1234-5678-abcd-123456789012",
        "requester": "U_REQUESTER",
        "action": "create_s3_bucket",
        "name": "demo",
        "ttl_hours": 2,
        "env": "dev",
    }


@mock_aws
def test_bucket_security_and_cleanup(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    s3 = boto3.client("s3")
    result = create_bucket(request(), s3)
    bucket = result["bucket"]
    assert all(s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"].values())
    assert (
        s3.get_bucket_encryption(Bucket=bucket)["ServerSideEncryptionConfiguration"]["Rules"][0][
            "ApplyServerSideEncryptionByDefault"
        ]["SSEAlgorithm"]
        == "AES256"
    )
    tags = {tag["Key"]: tag["Value"] for tag in s3.get_bucket_tagging(Bucket=bucket)["TagSet"]}
    assert tags["managed_by"] == "opspilot"
    assert tags["owner"] == "U_REQUESTER"
    assert delete_empty_bucket(bucket, s3) == "deleted"


@mock_aws
def test_nonempty_bucket_is_preserved(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    s3 = boto3.client("s3")
    bucket = create_bucket(request(), s3)["bucket"]
    s3.put_object(Bucket=bucket, Key="keep-me", Body=b"data")
    with pytest.raises(ClientError):
        delete_empty_bucket(bucket, s3)
    assert s3.get_object(Bucket=bucket, Key="keep-me")["Body"].read() == b"data"


@mock_aws
def test_nonmanaged_bucket_is_preserved(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    s3 = boto3.client("s3")
    s3.create_bucket(Bucket="opspilot-other")
    s3.put_bucket_tagging(
        Bucket="opspilot-other", Tagging={"TagSet": [{"Key": "managed_by", "Value": "other"}]}
    )
    with pytest.raises(ValueError):
        delete_empty_bucket("opspilot-other", s3)


@mock_aws
def test_hourly_cleanup_expired_only(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    result = create_bucket(request())
    item = {**request(), **result, "status": "provisioned"}
    audit.save_request(item)
    assert cleanup.run() == []
    assert cleanup.run(datetime.now(timezone.utc) + timedelta(hours=3))[0]["status"] == "deleted"
    assert audit.get_request(item["request_id"])["status"] == "deleted"


@mock_aws
def test_dynamodb_conditional_transition(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "dynamodb")
    monkeypatch.setenv("REQUESTS_TABLE", "requests")
    dynamodb = boto3.resource("dynamodb")
    dynamodb.create_table(
        TableName="requests",
        KeySchema=[{"AttributeName": "request_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "request_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    audit.save_request({**request(), "status": "pending"})
    assert audit.transition(request()["request_id"], "pending", "executing")
    assert not audit.transition(request()["request_id"], "pending", "executing")


@mock_aws
def test_dynamodb_item_can_execute_with_decimal_ttl(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "dynamodb")
    monkeypatch.setenv("REQUESTS_TABLE", "requests")
    monkeypatch.setenv("DRY_RUN", "true")
    dynamodb = boto3.resource("dynamodb")
    dynamodb.create_table(
        TableName="requests",
        KeySchema=[{"AttributeName": "request_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "request_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    audit.save_request({**request(), "status": "executing"})
    stored = audit.get_request(request()["request_id"])
    assert create_bucket(stored)["dry_run"] is True
