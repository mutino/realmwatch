import functools
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import server


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = server.DATA
        server.DATA = Path(self.temp.name) / "status.json"
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(server.Handler, directory=str(server.ROOT)))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.http.server_address[1])

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        server.DATA = self.previous
        self.temp.cleanup()

    def test_snapshot_is_live_then_stale_without_losing_data(self):
        for at, expected in [(datetime.now(timezone.utc).isoformat(), False), ("2020-01-01T00:00:00+00:00", True)]:
            server.DATA.write_text(json.dumps({"updated_at": at, "servers": [{"name": "North"}]}))
            with urllib.request.urlopen(self.base + "/api/status") as response:
                data = json.load(response)
                self.assertEqual(data["stale"], expected)
                self.assertEqual(data["servers"][0]["name"], "North")
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_only_public_files_are_served_and_missing_data_is_explicit(self):
        with urllib.request.urlopen(self.base + "/") as response:
            self.assertIn(b"Realmwatch", response.read())
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        for path, code in [("/history.sqlite3", 404), ("/../collector.py", 404), ("/api/status", 503)]:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(self.base + path)
            self.assertEqual(caught.exception.code, code)
            caught.exception.close()

    def test_gateway_secret_protects_page_and_activity(self):
        previous = server.UPSTREAM_SECRET
        server.UPSTREAM_SECRET = "test-only-gateway-secret"
        try:
            server.DATA.write_text(json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "servers": []}))
            for path in ("/", "/api/status"):
                for secret in ("", "wrong"):
                    request = urllib.request.Request(self.base + path, headers={"X-Realmwatch-Upstream": secret})
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(request)
                    self.assertEqual(caught.exception.code, 403)
                    caught.exception.close()
                request = urllib.request.Request(self.base + path, headers={"X-Realmwatch-Upstream": server.UPSTREAM_SECRET})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 200)
            with urllib.request.urlopen(self.base + "/healthz") as response:
                self.assertTrue(json.load(response)["ok"])
        finally:
            server.UPSTREAM_SECRET = previous


if __name__ == "__main__":
    unittest.main()
