import logging
from datetime import datetime, timezone
from app import audit
from app.executor import delete_empty_bucket

logger = logging.getLogger(__name__)


def run(now=None):
    now = now or datetime.now(timezone.utc)
    results = []
    for item in audit.active_requests():
        if item.get("dry_run") or datetime.fromisoformat(item["ttl_expiry"]) > now:
            continue
        expected_status = item.get("status", "provisioned")
        if not audit.transition(item["request_id"], expected_status, "deleting"):
            continue
        audit.record(
            item["request_id"], "cleanup", item["action"], {"bucket": item["bucket"]}, "deleting"
        )
        try:
            result = delete_empty_bucket(
                item["bucket"], expired_at=now, request_id=item["request_id"]
            )
            if result == "dry_run":
                audit.transition(item["request_id"], "deleting", "provisioned")
                audit.record(
                    item["request_id"],
                    "cleanup",
                    item["action"],
                    {"bucket": item["bucket"]},
                    "provisioned",
                    "Deletion skipped: dry run",
                )
                continue
            audit.transition(item["request_id"], "deleting", "deleted")
            audit.record(
                item["request_id"],
                "cleanup",
                item["action"],
                {"bucket": item["bucket"]},
                "deleted",
                result,
            )
            results.append({"bucket": item["bucket"], "status": "deleted"})
        except Exception as exc:
            logger.exception("Failed to delete %s", item["bucket"])
            audit.transition(
                item["request_id"], "deleting", "cleanup_failed", error=type(exc).__name__
            )
            audit.record(
                item["request_id"],
                "cleanup",
                item["action"],
                {"bucket": item["bucket"]},
                "cleanup_failed",
                type(exc).__name__,
            )
            results.append({"bucket": item["bucket"], "status": "cleanup_failed"})
    return results


def handler(event, context):
    return {"results": run()}
