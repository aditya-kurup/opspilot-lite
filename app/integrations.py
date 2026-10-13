"""Optional Jenkins and ServiceNow lifecycle integrations."""
from __future__ import annotations
import base64, json, os, urllib.parse, urllib.request
from typing import Any

def _headers() -> dict[str, str]:
    token = base64.b64encode(f"{os.getenv('SERVICENOW_USER','')}:{os.getenv('SERVICENOW_PASSWORD','')}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

def create_servicenow_record(item: dict[str, Any]) -> str | None:
    base = os.getenv("SERVICENOW_URL", "").rstrip("/")
    if not base: return None
    table = os.getenv("SERVICENOW_TABLE", "sc_request")
    payload = {"short_description": f"OpsPilot provisioning {item['request_id'][:8]}", "description": json.dumps(item, default=str), "u_request_id": item["request_id"]}
    request = urllib.request.Request(f"{base}/api/now/table/{table}", data=json.dumps(payload).encode(), headers=_headers(), method="POST")
    with urllib.request.urlopen(request, timeout=15) as response: result = json.loads(response.read().decode())
    return (result.get("result") or {}).get("sys_id")

def trigger_jenkins(request_id: str) -> bool:
    base = os.getenv("JENKINS_URL", "").rstrip("/")
    if not base: return False
    job = urllib.parse.quote(os.getenv("JENKINS_JOB", "opspilot-provision"), safe="")
    query = urllib.parse.urlencode({"REQUEST_ID": request_id})
    request = urllib.request.Request(f"{base}/job/{job}/buildWithParameters?{query}", headers={"Authorization": f"Bearer {os.getenv('JENKINS_TOKEN', '')}"}, method="POST")
    with urllib.request.urlopen(request, timeout=15): return True
