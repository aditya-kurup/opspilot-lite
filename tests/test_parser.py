import pytest
from pydantic import ValidationError
from app import llm
from app.parser import parse_request, ProvisionRequest


def test_valid_request():
    parsed = parse_request("Create a test bucket named My_Demo for 4 hours", llm.parse)
    assert parsed.name == "my-demo"
    assert parsed.ttl_hours == 4


@pytest.mark.parametrize(
    "field,value",
    [
        ("action", "delete_all"),
        ("ttl_hours", 73),
        ("ttl_hours", 0),
        ("ttl_hours", "2"),
        ("env", "prod"),
        ("name", "!!!"),
        ("unknown", "oops"),
    ],
)
def test_schema_rejects_unsafe_output(field, value):
    data = {"action": "create_s3_bucket", "name": "demo", "ttl_hours": 2, "env": "dev"}
    data[field] = value
    with pytest.raises(ValidationError):
        ProvisionRequest.model_validate(data)


@pytest.mark.parametrize(
    "text",
    [
        "create a production bucket named demo for 2 hours",
        "create a dev bucket named demo for 200 hours",
        "delete every bucket",
        "create a bucket named demo",
    ],
)
def test_mock_does_not_silently_fix_invalid_requests(text):
    with pytest.raises(ValidationError):
        parse_request(text, llm.parse)


def test_redacts_common_secrets_and_email():
    output = llm.redact(
        "owner alice@example.com token=hidden AKIA1234567890123456 xoxb-demo-secret"
    )
    for secret in ("alice@example.com", "hidden", "AKIA1234567890123456", "xoxb-demo-secret"):
        assert secret not in output


def test_bedrock_wrapper(monkeypatch):
    from unittest.mock import Mock

    client = Mock()
    client.converse.return_value = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": '{"action":"create_s3_bucket","name":"demo","ttl_hours":2,"env":"dev"}'
                    }
                ]
            }
        }
    }
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setattr(llm.boto3, "client", lambda _: client)
    result = parse_request("Create a dev bucket named demo for 2 hours token=secret123", llm.parse)
    assert result.name == "demo"
    assert "secret123" not in str(client.converse.call_args)
