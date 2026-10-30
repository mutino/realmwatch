"""Unprivileged, read-only dashboard HTTP server; no Docker socket or credentials."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import hmac
import time
from datetime import datetime, timezone

ROOT = Path(__file__).parent / "web"
DATA = Path(os.getenv("STATUS_FILE", "/data/status.json"))
SECRET_FILE = os.getenv("UPSTREAM_SECRET_FILE")
UPSTREAM_SECRET = Path(SECRET_FILE).read_text().strip() if SECRET_FILE else None
if SECRET_FILE and not UPSTREAM_SECRET:
    raise RuntimeError("Upstream secret must not be empty")


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header("Cache-Control", "no-store" if self.path.startswith('/api/') else "no-cache")
        super().end_headers()

    def json_response(self, code, body):
        encoded = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if UPSTREAM_SECRET and path != "/healthz" and not hmac.compare_digest(
            self.headers.get("X-Realmwatch-Upstream", ""), UPSTREAM_SECRET
        ):
            return self.json_response(403, {"error": "Use the authenticated HTTPS gateway."})
        if path in ("/api/status", "/healthz"):
            try:
                data = json.loads(DATA.read_text())
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(data["updated_at"])).total_seconds()
                data["stale"] = age > 60
                if path == "/healthz":
                    return self.json_response(503 if age > 90 else 200, {"ok": age <= 90, "age_seconds": round(age)})
                return self.json_response(200, data)
            except (OSError, ValueError, KeyError):
                return self.json_response(503, {"error": "The first server scan is still running. Please try again shortly."})
        if path not in ("/", "/index.html", "/app.js", "/style.css", "/favicon.svg"):
            return self.send_error(404)
        return super().do_GET()


if __name__ == "__main__":
    server = ThreadingHTTPServer((os.getenv("BIND_HOST", "127.0.0.1"), int(os.getenv("PORT", "8080"))), partial(Handler, directory=str(ROOT)))
    server.serve_forever()
