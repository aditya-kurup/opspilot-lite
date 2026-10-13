"""Local browser simulator. Never use this unauthenticated server for real AWS actions."""

import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app import audit
from app.handlers import decide, process_request

MESSAGES = []


class DemoSlack:
    def chat_postMessage(self, **kwargs):
        MESSAGES.append({"type": "message", **kwargs})

    def chat_postEphemeral(self, **kwargs):
        MESSAGES.append({"type": "ephemeral", **kwargs})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            body = (Path(__file__).parent.parent / "demo" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/assets/"):
            if self.path not in {"/assets/style.css", "/assets/app.js"}:
                return self.respond(404, {"error": "Not found"})
            asset = Path(__file__).parent.parent / "demo" / self.path.lstrip("/")
            if not asset.is_file() or asset.suffix not in {".css", ".js"}:
                return self.respond(404, {"error": "Not found"})
            body = asset.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/css; charset=utf-8"
                if asset.suffix == ".css"
                else "text/javascript; charset=utf-8",
            )
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/state":
            with audit._db() as db:
                requests = [
                    json.loads(row[0])
                    for row in db.execute("SELECT payload FROM requests ORDER BY rowid DESC")
                ]
                entries = [
                    json.loads(row[0])
                    for row in db.execute("SELECT payload FROM audit ORDER BY id DESC LIMIT 100")
                ]
            self.respond(200, {"requests": requests, "audit": entries, "messages": MESSAGES[-50:]})
        else:
            self.respond(404, {"error": "Not found"})

    def do_POST(self):
        # Same-origin writes only; this local simulator has no credentials or real AWS permissions.
        if self.headers.get("Origin") not in {
            None,
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        }:
            return self.respond(403, {"error": "Invalid origin"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 4096:
                return self.respond(413, {"error": "Request too large"})
            data = json.loads(self.rfile.read(size))
            if self.path == "/api/reset":
                with audit._db() as db:
                    db.execute("DELETE FROM audit")
                    db.execute("DELETE FROM requests")
                MESSAGES.clear()
                self.respond(200, {"message": "Demo state cleared."})
            elif self.path == "/api/request":
                process_request(
                    {
                        "request_id": str(uuid.uuid4()),
                        "requester": "U_REQUESTER",
                        "channel": "demo",
                        "text": data["text"],
                    },
                    DemoSlack(),
                )
                self.respond(200, {"message": "Request processed."})
            elif self.path == "/api/decision":
                if data["actor"] not in {"U_REQUESTER", "U_APPROVER", "U_VISITOR"}:
                    raise ValueError("Invalid actor")
                message = decide(
                    data["request_id"], data["actor"], data["decision"], DemoSlack(), "demo"
                )
                self.respond(200, {"message": message})
            else:
                self.respond(404, {"error": "Not found"})
        except (KeyError, ValueError, TypeError):
            self.respond(400, {"error": "Invalid request"})


def main():
    os.environ.update(
        STORAGE_BACKEND="sqlite",
        SQLITE_PATH="demo.sqlite3",
        LLM_PROVIDER="mock",
        DRY_RUN="true",
        APPROVER_USER_IDS="U_APPROVER",
    )
    audit._db().close()
    print("OpsPilot Lite browser demo: http://127.0.0.1:8000 (mock parser, dry-run AWS)")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()


if __name__ == "__main__":
    main()
