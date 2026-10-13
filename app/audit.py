import json
import os
import sqlite3
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db():
    db = sqlite3.connect(os.getenv("SQLITE_PATH", "opspilot.sqlite3"))
    db.execute("CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, payload TEXT NOT NULL)"
    )
    return db


def table():
    return boto3.resource("dynamodb").Table(os.environ["REQUESTS_TABLE"])


def save_request(item: dict) -> None:
    if os.getenv("STORAGE_BACKEND") == "sqlite":
        with _db() as db:
            db.execute("INSERT INTO requests VALUES (?, ?)", (item["request_id"], json.dumps(item)))
    else:
        table().put_item(Item=item, ConditionExpression="attribute_not_exists(request_id)")


def get_request(request_id: str) -> dict | None:
    if os.getenv("STORAGE_BACKEND") == "sqlite":
        with _db() as db:
            row = db.execute("SELECT payload FROM requests WHERE id=?", (request_id,)).fetchone()
            return json.loads(row[0]) if row else None
    return table().get_item(Key={"request_id": request_id}, ConsistentRead=True).get("Item")


def transition(request_id: str, expected: str, status: str, **updates) -> bool:
    if os.getenv("STORAGE_BACKEND") == "sqlite":
        with _db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM requests WHERE id=?", (request_id,)).fetchone()
            if not row:
                return False
            item = json.loads(row[0])
            if item["status"] != expected:
                return False
            item.update(status=status, **updates)
            db.execute("UPDATE requests SET payload=? WHERE id=?", (json.dumps(item), request_id))
            return True
    from botocore.exceptions import ClientError

    names = {"#s": "status"}
    values = {":old": expected, ":new": status}
    parts = ["#s=:new"]
    for index, (key, value) in enumerate(updates.items()):
        names[f"#k{index}"] = key
        values[f":v{index}"] = value
        parts.append(f"#k{index}=:v{index}")
    try:
        table().update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET " + ", ".join(parts),
            ConditionExpression="#s=:old",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def update_fields(request_id: str, expected: str, **updates) -> bool:
    """Update metadata while retaining the current state (used for delivery retries)."""
    return transition(request_id, expected, expected, **updates)


def record(
    request_id: str, actor: str, action: str, params: dict, status: str, result: str = ""
) -> None:
    entry = {
        "request_id": request_id,
        "timestamp": now(),
        "actor": actor,
        "action": action,
        "params": params,
        "status": status,
        "result": result,
    }
    if os.getenv("STORAGE_BACKEND") == "sqlite":
        with _db() as db:
            db.execute(
                "INSERT INTO audit (request_id,payload) VALUES (?,?)",
                (request_id, json.dumps(entry)),
            )
    else:
        boto3.resource("dynamodb").Table(os.environ["AUDIT_TABLE"]).put_item(Item=entry)


def active_requests() -> list[dict]:
    if os.getenv("STORAGE_BACKEND") == "sqlite":
        with _db() as db:
            return [
                json.loads(row[0])
                for row in db.execute("SELECT payload FROM requests")
                if json.loads(row[0])["status"] in {"provisioned", "cleanup_failed"}
            ]
    items = []
    for status in ("provisioned", "cleanup_failed"):
        query = {"IndexName": "status-index", "KeyConditionExpression": Key("status").eq(status)}
        while True:
            result = table().query(**query)
            items.extend(result["Items"])
            if "LastEvaluatedKey" not in result:
                break
            query["ExclusiveStartKey"] = result["LastEvaluatedKey"]
    return items
