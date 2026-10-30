import json
from pathlib import Path
import tempfile
import unittest
from collector import History


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.history = History(Path(self.temp.name) / "test.sqlite3")
        self.tick = 0

    def tearDown(self):
        self.history.db.close()
        self.temp.cleanup()

    def log(self, message, server="north"):
        self.tick += 1
        self.history.process(server, "container-" + server, f"2026-10-19T00:00:{self.tick:02d}.123456789Z", message)

    def join(self, name="Example Viking", peer="10001", server="north"):
        self.log("Got connection SteamID " + peer, server)
        self.log("Got handshake from client " + peer, server)
        self.log(f"Got character ZDOID from {name} : -123:1", server)

    def test_named_login_and_exact_logout(self):
        self.join()
        self.log("Closing socket 10001")
        item = self.history.profiles()[0]
        self.assertEqual(item["name"], "Example Viking")
        self.assertFalse(item["online"])
        self.assertEqual(item["logout_reason"], "log")
        self.assertEqual(item["sessions"], 1)
        self.assertTrue(item["last_logout"].endswith("+00:00"))

    def test_death_and_respawn_are_not_duplicate_logins(self):
        self.join()
        self.log("Got character ZDOID from Example Viking : 0:0")
        self.log("Got character ZDOID from Example Viking : 123:99")
        self.assertEqual(self.history.profiles()[0]["sessions"], 1)
        self.assertTrue(self.history.profiles()[0]["online"])

    def test_repeated_ingestion_is_idempotent(self):
        self.join()
        self.history.process("north", "container-north", "2026-10-19T00:00:03.123456789Z", "Got character ZDOID from Example Viking : -123:1")
        self.assertEqual(self.history.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 1)

    def test_simultaneous_unknown_connections_do_not_get_wrong_logout(self):
        self.log("Got connection SteamID 111")
        self.log("Got connection SteamID 222")
        self.log("Got character ZDOID from Viking : -123:1")
        self.log("Closing socket 111")
        self.assertTrue(self.history.profiles()[0]["online"])
        self.assertIsNone(self.history.db.execute("SELECT peer FROM sessions").fetchone()[0])

    def test_restart_closes_sessions_with_explicit_reason(self):
        self.join()
        self.log("Valheim version: 1.0.20")
        self.assertFalse(self.history.profiles()[0]["online"])
        self.assertEqual(self.history.profiles()[0]["logout_reason"], "server_restart")

    def test_character_can_have_distinct_realms_and_multiple_visits(self):
        self.join(server="north")
        self.log("Closing socket 10001", "north")
        self.join(server="north")
        self.join(server="prime")
        profiles = {p["server"]: p for p in self.history.profiles()}
        self.assertEqual(profiles["north"]["sessions"], 2)
        self.assertEqual(profiles["prime"]["sessions"], 1)

    def test_log_tail_keeps_partial_record_for_next_scan(self):
        log = Path(self.temp.name) / "container-json.log"
        first = json.dumps({"time":"2026-10-19T00:00:00Z", "log":"Got connection SteamID 111"}) + "\n"
        second = json.dumps({"time":"2026-10-19T00:00:01Z", "log":"Got character ZDOID from <Viking & Co> : -123:1"}) + "\n"
        log.write_text(first + second[:30])
        container = {"Id":"c", "LogPath":str(log)}
        self.history.ingest("north", container)
        self.assertEqual(self.history.profiles(), [])
        with log.open("a") as f:
            f.write(second[30:])
        self.history.ingest("north", container)
        self.history.ingest("north", container)
        self.assertEqual(self.history.profiles()[0]["name"], "<Viking & Co>")
        self.assertEqual(self.history.profiles()[0]["sessions"], 1)


if __name__ == "__main__":
    unittest.main()
