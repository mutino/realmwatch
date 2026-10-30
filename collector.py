#!/usr/bin/env python3
"""Local, read-only Docker collector. Only sanitized JSON is served to the web app."""
import concurrent.futures
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from portals import snapshot as portal_snapshot

UTC = timezone.utc
LOG = logging.getLogger("realmwatch")
EVENT_MARKERS = ("Got connection SteamID", "Got handshake from client", "Got character ZDOID from", "Closing socket", "Valheim version:")


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).isoformat(timespec="milliseconds")


def now():
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class History:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, offset INTEGER, first_time TEXT);
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS connections (
                server TEXT, peer TEXT, connected_at TEXT, session_id INTEGER,
                PRIMARY KEY(server,peer));
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY, server TEXT NOT NULL, player TEXT NOT NULL,
                peer TEXT, login_at TEXT NOT NULL, logout_at TEXT, logout_reason TEXT);
            CREATE INDEX IF NOT EXISTS session_server ON sessions(server,login_at);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, server TEXT, player TEXT, kind TEXT, at TEXT, reason TEXT);
            CREATE INDEX IF NOT EXISTS event_time ON events(at);
        """)

    def end_session(self, row, at, reason):
        if not row or row["logout_at"] is not None:
            return
        # Never invent a logout earlier than the recorded login.
        at = max(at, row["login_at"])
        self.db.execute("UPDATE sessions SET logout_at=?,logout_reason=? WHERE id=?", (at, reason, row["id"]))
        self.db.execute("INSERT INTO events(server,player,kind,at,reason) VALUES(?,?,?,?,?)", (row["server"], row["player"], "leave", at, reason))

    def end_all(self, server, at, reason):
        for row in self.db.execute("SELECT * FROM sessions WHERE server=? AND logout_at IS NULL", (server,)).fetchall():
            self.end_session(row, at, reason)
        self.db.execute("DELETE FROM connections WHERE server=?", (server,))

    def process(self, server, container_id, at, message):
        if not any(marker in message for marker in EVENT_MARKERS):
            return
        at = timestamp(at)
        fingerprint = hashlib.sha256((container_id + at + message.strip()).encode()).hexdigest()
        if not self.db.execute("INSERT OR IGNORE INTO seen VALUES(?)", (fingerprint,)).rowcount:
            return
        if "Valheim version:" in message:
            self.end_all(server, at, "server_restart")
            return
        match = re.search(r"(?:Got connection SteamID|Got handshake from client)\s+([^\s]+)", message)
        if match:
            peer = match[1]
            if "Got connection SteamID" in message:
                conn = self.db.execute("SELECT session_id FROM connections WHERE server=? AND peer=?", (server, peer)).fetchone()
                if conn and conn[0]:
                    self.end_session(self.db.execute("SELECT * FROM sessions WHERE id=?", (conn[0],)).fetchone(), at, "reconnected")
                    self.db.execute("DELETE FROM connections WHERE server=? AND peer=?", (server, peer))
            self.db.execute("INSERT OR IGNORE INTO connections VALUES(?,?,?,NULL)", (server, peer, at))
            return
        match = re.search(r"Got character ZDOID from (.+?)\s+:\s*(-?\d+):(\d+)", message)
        if match:
            if (match[2], match[3]) == ("0", "0"):
                return  # A death, not a new login.
            player = match[1].strip()
            if self.db.execute("SELECT 1 FROM sessions WHERE server=? AND player=? AND logout_at IS NULL", (server, player)).fetchone():
                return  # Respawns and duplicated Unity/BepInEx log messages.
            cutoff = (datetime.fromisoformat(at) - timedelta(minutes=5)).isoformat(timespec="milliseconds")
            pending = self.db.execute("SELECT * FROM connections WHERE server=? AND session_id IS NULL AND connected_at>=? AND connected_at<=?", (server, cutoff, at)).fetchall()
            # Don't assign the wrong identity when simultaneous joins are ambiguous.
            peer = pending[0]["peer"] if len(pending) == 1 else None
            sid = self.db.execute("INSERT INTO sessions(server,player,peer,login_at) VALUES(?,?,?,?)", (server, player, peer, at)).lastrowid
            if peer:
                self.db.execute("UPDATE connections SET session_id=? WHERE server=? AND peer=?", (sid, server, peer))
            self.db.execute("INSERT INTO events(server,player,kind,at,reason) VALUES(?,?,?,?,?)", (server, player, "join", at, "log"))
            return
        match = re.search(r"Closing socket\s+([^\s]+)", message)
        if match:
            conn = self.db.execute("SELECT * FROM connections WHERE server=? AND peer=?", (server, match[1])).fetchone()
            if conn and conn["session_id"]:
                self.end_session(self.db.execute("SELECT * FROM sessions WHERE id=?", (conn["session_id"],)).fetchone(), at, "log")
            self.db.execute("DELETE FROM connections WHERE server=? AND peer=?", (server, match[1]))

    def ingest(self, server, container):
        logpath = container.get("LogPath")
        if not logpath:
            return "No Docker JSON log available"
        paths = sorted((p for p in Path(logpath).parent.glob(Path(logpath).name + "*") if p.is_file() and not p.name.endswith(".gz")), key=lambda p: p.stat().st_mtime)
        for path in paths:
            stat = path.stat()
            source_id = f"{container['Id']}:{stat.st_dev}:{stat.st_ino}"
            row = self.db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            offset = row["offset"] if row and row["offset"] <= stat.st_size else 0
            first = row["first_time"] if row else None
            with path.open("rb") as source:
                source.seek(offset)
                while True:
                    before = source.tell()
                    raw = source.readline()
                    if not raw:
                        break
                    if not raw.endswith(b"\n"):
                        source.seek(before)
                        break  # Docker is still writing this record.
                    if first is not None and not any(m.encode() in raw for m in EVENT_MARKERS):
                        continue
                    try:
                        record = json.loads(raw)
                        at, message = record["time"], record.get("log", "")
                        if first is None:
                            first = timestamp(at)
                        self.process(server, container["Id"], at, message)
                    except (ValueError, KeyError):
                        continue
                offset = source.tell()
            self.db.execute("INSERT OR REPLACE INTO sources VALUES(?,?,?)", (source_id, offset, first))
        return None

    def profiles(self):
        rows = self.db.execute("SELECT * FROM sessions ORDER BY login_at").fetchall()
        profiles = {}
        for row in rows:
            key = (row["server"], row["player"])
            item = profiles.setdefault(key, dict(server=row["server"], name=row["player"], last_login=None, last_logout=None, logout_reason=None, online=False, sessions=0))
            item["sessions"] += 1
            item["last_login"] = row["login_at"]
            if row["logout_at"] and (not item["last_logout"] or row["logout_at"] > item["last_logout"]):
                item["last_logout"], item["logout_reason"] = row["logout_at"], row["logout_reason"]
            item["online"] = row["logout_at"] is None
        return sorted(profiles.values(), key=lambda p: p["last_login"], reverse=True)


def discover():
    listing = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.ID}} {{.Image}} {{.Names}}"], text=True, timeout=15)
    ids = [line.split()[0] for line in listing.splitlines() if "valheim-server" in line.split()[1] and "valheim-watch" not in line]
    return json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True, timeout=15)) if ids else []


def query(container):
    if container["State"]["Status"] != "running":
        return {"error": "Container is not running"}
    try:
        env = dict(e.split("=", 1) for e in container["Config"]["Env"] if "=" in e)
        result = subprocess.run(["docker", "exec", container["Id"], "valheim-status", "--host", "127.0.0.1", "--port", env.get("SERVER_PORT", "2456")], capture_output=True, text=True, timeout=8)
        # This utility deliberately exits with the player count, not just zero.
        data = json.loads(result.stdout)
        return {k: data.get(k) for k in ("error", "server_name", "player_count", "last_status_update", "keywords", "password_protected")}
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        return {"error": "Live server query unavailable (" + type(exc).__name__ + ")"}


def collect(history, output):
    containers = discover()
    servers = []
    for container in containers:
        sid = container["Name"].lstrip("/")
        env = dict(e.split("=", 1) for e in container["Config"]["Env"] if "=" in e)
        previous = history.db.execute("SELECT value FROM metadata WHERE key=?", ("container:" + sid,)).fetchone()
        if previous and previous[0] != container["Id"]:
            history.end_all(sid, timestamp(container["Created"]), "server_restart")
        history.db.execute("INSERT OR REPLACE INTO metadata VALUES(?,?)", ("container:" + sid, container["Id"]))
        log_error = history.ingest(sid, container)
        if container["State"]["Status"] != "running":
            finish = container["State"].get("FinishedAt", "")
            history.end_all(sid, timestamp(finish) if finish and not finish.startswith("0001") else now(), "server_stopped")
        servers.append(dict(id=sid, name=env.get("SERVER_NAME", sid), world=env.get("WORLD_NAME", "Unknown world"), container_state=container["State"]["Status"], started_at=container["State"].get("StartedAt"), log_error=log_error))
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        statuses = list(executor.map(query, containers))
    for server, container in zip(servers, containers):
        server["portal_registry"] = portal_snapshot(container)
    checked_at = now()
    for server, status in zip(servers, statuses):
        server["status"] = "online" if not status.get("error") else ("offline" if server["container_state"] != "running" else "unreachable")
        server["query_error"] = status.get("error")
        count = status.get("player_count")
        server["player_count"] = int(count) if count is not None and not status.get("error") else None
        server["checked_at"] = checked_at
        if not status.get("error") and count == 0:
            history.end_all(server["id"], checked_at, "detected_offline")
        # Mark names unconfirmed when the server can't currently be queried.
        server["names_confirmed"] = server["status"] == "online"
    history.db.commit()
    profiles = history.profiles()
    for server in servers:
        active = [p for p in profiles if p["server"] == server["id"] and p["online"]]
        if server["player_count"] is not None and len(active) > server["player_count"]:
            server["names_confirmed"] = False
        for profile in active:
            profile["confirmed"] = server["names_confirmed"]
        server["players"] = [p["name"] for p in active] if server["names_confirmed"] else []
        server["unnamed_players"] = max(0, (server["player_count"] or 0) - len(server["players"]))
    events = [dict(r) for r in history.db.execute("SELECT server,player,kind,at,reason FROM events ORDER BY at DESC,id DESC LIMIT 200")]
    history_start = history.db.execute("SELECT MIN(first_time) FROM sources").fetchone()[0]
    midnight = datetime.now(ZoneInfo("Europe/London")).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC).isoformat(timespec="milliseconds")
    joins_today = history.db.execute("SELECT COUNT(*) FROM events WHERE kind='join' AND at>=?", (midnight,)).fetchone()[0]
    payload = dict(updated_at=checked_at, refresh_seconds=15, history_start=history_start, joins_today=joins_today, servers=sorted(servers, key=lambda s:s["name"].casefold()), players=profiles, events=events)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False))
    temporary.chmod(0o644)
    os.replace(temporary, output)
    LOG.info("Collected %d servers, %d player profiles", len(servers), len(profiles))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="/opt/realmwatch/data")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    data = Path(args.data_dir)
    data.mkdir(parents=True, exist_ok=True)
    public = data / "public"
    public.mkdir(mode=0o755, exist_ok=True)
    public.chmod(0o755)
    history = History(data / "history.sqlite3")
    while True:
        try:
            collect(history, public / "status.json")
        except Exception:
            history.db.rollback()
            LOG.exception("Collection failed; previous snapshot retained")
            if args.once:
                raise
        if args.once:
            return
        time.sleep(15)


if __name__ == "__main__":
    main()
