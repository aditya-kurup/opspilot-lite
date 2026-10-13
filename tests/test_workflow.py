from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from app import audit
from app.handlers import decide, process_request


def pending():
    client = Mock()
    process_request(
        {
            "request_id": "abc12345-1234-5678-abcd-123456789012",
            "requester": "U_REQUESTER",
            "channel": "C_DEMO",
            "text": "Create a dev bucket named demo for 2 hours",
        },
        client,
    )
    return client


def test_approval_and_duplicate_click():
    client = pending()
    request_id = "abc12345-1234-5678-abcd-123456789012"
    assert decide(request_id, "U_APPROVER", "approve", client, "C_DEMO") == "Approved."
    assert audit.get_request(request_id)["status"] == "provisioned"
    assert audit.get_request(request_id)["dry_run"] is True
    assert "already" in decide(request_id, "U_APPROVER", "approve", client, "C_DEMO")
    with audit._db() as db:
        assert db.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 3


def test_requester_and_unlisted_user_cannot_approve(monkeypatch):
    client = pending()
    monkeypatch.setenv("APPROVER_USER_IDS", "U_APPROVER,U_REQUESTER")
    request_id = "abc12345-1234-5678-abcd-123456789012"
    for actor in ("U_REQUESTER", "U_VISITOR"):
        assert "not authorized" in decide(request_id, actor, "approve", client, "C_DEMO")
    assert audit.get_request(request_id)["status"] == "pending"


def test_reject():
    client = pending()
    request_id = "abc12345-1234-5678-abcd-123456789012"
    decide(request_id, "U_APPROVER", "reject", client, "C_DEMO")
    assert audit.get_request(request_id)["status"] == "rejected"


def test_wrong_channel():
    client = pending()
    assert "channel" in decide(
        "abc12345-1234-5678-abcd-123456789012", "U_APPROVER", "approve", client, "WRONG"
    )


def test_only_one_concurrent_claim():
    pending()
    with ThreadPoolExecutor(max_workers=5) as pool:
        outcomes = list(
            pool.map(
                lambda _: audit.transition(
                    "abc12345-1234-5678-abcd-123456789012", "pending", "executing"
                ),
                range(5),
            )
        )
    assert sum(outcomes) == 1


def test_duplicate_queue_delivery():
    client = pending()
    process_request(
        {
            "request_id": "abc12345-1234-5678-abcd-123456789012",
            "requester": "U_REQUESTER",
            "channel": "C_DEMO",
            "text": "Create a dev bucket named demo for 2 hours",
        },
        client,
    )
    assert client.chat_postMessage.call_count == 1
