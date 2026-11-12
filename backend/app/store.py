"""Small persistent store (SQLite, Python standard library: no new dependency).

Keeps what the passenger did (actions), claim statuses they reported,
their travel preferences, and community reports. Railway events stay in the
simulated data source. Set STORE_PATH to a file to keep data between restarts;
the default ":memory:" forgets everything when the server stops (safe for demos).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (jid TEXT, plan_id TEXT, plan_kind TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS claims (jid TEXT, item_id TEXT, status TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS preferences (jid TEXT PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT);
"""


class Store:
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("STORE_PATH", ":memory:")
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)

    def _exec(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur.fetchall()

    # actions
    def add_action(self, jid: str, plan_id: str, plan_kind: str, at: str) -> dict:
        self._exec("INSERT INTO actions VALUES (?,?,?,?)", (jid, plan_id, plan_kind, at))
        return {"plan_id": plan_id, "plan_kind": plan_kind, "at": at}

    def actions(self, jid: str) -> list[dict]:
        return [dict(r) for r in self._exec("SELECT plan_id, plan_kind, at FROM actions WHERE jid=? ORDER BY rowid", (jid,))]

    # claims (reported by the passenger; never inferred)
    def add_claim(self, jid: str, item_id: str, status: str, at: str) -> dict:
        self._exec("INSERT INTO claims VALUES (?,?,?,?)", (jid, item_id, status, at))
        return {"item_id": item_id, "status": status, "at": at}

    def claims(self, jid: str) -> list[dict]:
        return [dict(r) for r in self._exec("SELECT item_id, status, at FROM claims WHERE jid=? ORDER BY rowid", (jid,))]

    # preferences
    def get_prefs(self, jid: str) -> dict | None:
        rows = self._exec("SELECT data FROM preferences WHERE jid=?", (jid,))
        return json.loads(rows[0]["data"]) if rows else None

    def set_prefs(self, jid: str, data: dict) -> None:
        self._exec("INSERT OR REPLACE INTO preferences VALUES (?,?)", (jid, json.dumps(data)))

    # community reports
    def add_report(self, data: dict) -> int:
        with self.lock:
            cur = self.db.execute("INSERT INTO reports (data) VALUES (?)", (json.dumps(data),))
            self.db.commit()
            return cur.lastrowid

    def update_report(self, rid: int, data: dict) -> None:
        self._exec("UPDATE reports SET data=? WHERE id=?", (json.dumps(data), rid))

    def reports(self) -> list[tuple[int, dict]]:
        return [(r["id"], json.loads(r["data"])) for r in self._exec("SELECT id, data FROM reports ORDER BY id")]

    def clear_journey(self, jid: str) -> None:
        self._exec("DELETE FROM actions WHERE jid=?", (jid,))
        self._exec("DELETE FROM claims WHERE jid=?", (jid,))
        for rid, d in self.reports():
            if d.get("jid") == jid:
                self._exec("DELETE FROM reports WHERE id=?", (rid,))
