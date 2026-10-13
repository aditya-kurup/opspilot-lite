import hashlib
import hmac
import time
from unittest.mock import Mock
from urllib.parse import urlencode

from slack_bolt.request import BoltRequest
from slack_sdk.web import WebClient
from slack_sdk.web.slack_response import SlackResponse

from app import handlers


def test_slack_signature_and_fast_enqueue(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "ingress")
    monkeypatch.setattr(
        WebClient,
        "auth_test",
        lambda *args, **kwargs: SlackResponse(
            client=None,
            http_verb="POST",
            api_url="auth.test",
            req_args={},
            headers={},
            status_code=200,
            data={
                "ok": True,
                "team_id": "T_TEST",
                "user_id": "U_BOT",
                "bot_id": "B_TEST",
            },
        ),
    )
    enqueue = Mock()
    monkeypatch.setattr(handlers, "enqueue", enqueue)
    app = handlers.build_app()
    body = urlencode(
        {
            "command": "/provision",
            "text": "Create a dev bucket named demo for 2 hours",
            "user_id": "U_REQUESTER",
            "channel_id": "C_DEMO",
            "team_id": "T_TEST",
        }
    )
    timestamp = str(int(time.time()))
    signature = (
        "v0="
        + hmac.new(b"test-secret", f"v0:{timestamp}:{body}".encode(), hashlib.sha256).hexdigest()
    )
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "x-slack-request-timestamp": timestamp,
        "x-slack-signature": signature,
    }
    start = time.monotonic()
    response = app.dispatch(BoltRequest(body=body, headers=headers))
    assert response.status == 200
    assert time.monotonic() - start < 3
    enqueue.assert_called_once()
    headers["x-slack-signature"] = "v0=bad"
    assert app.dispatch(BoltRequest(body=body, headers=headers)).status == 401
    assert enqueue.call_count == 1


def test_old_slack_signature_is_rejected(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")
    app = handlers.build_app()
    body = "command=%2Fprovision"
    timestamp = str(int(time.time()) - 600)
    signature = (
        "v0="
        + hmac.new(b"test-secret", f"v0:{timestamp}:{body}".encode(), hashlib.sha256).hexdigest()
    )
    response = app.dispatch(
        BoltRequest(
            body=body,
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "x-slack-request-timestamp": timestamp,
                "x-slack-signature": signature,
            },
        )
    )
    assert response.status == 401
