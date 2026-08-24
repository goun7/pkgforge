"""Faz 5 (F5.12) — batch conversion queue persistence (SQLite).

The in-memory queue in core/api_server.py stays the hot path; this module is
the durable backing so pending items survive a restart. Items that were
'running' when the process died are restored as 'pending' because that work
never completed. Terminal items (done/error) are not resurrected.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from config import queue_db_path

_BUSY_TIMEOUT_MS = 5_000

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS queue ("
    " id TEXT PRIMARY KEY,"
    " path TEXT NOT NULL,"
    " name TEXT NOT NULL,"
    " status TEXT NOT NULL,"
    " priority INTEGER NOT NULL DEFAULT 0,"
    " message TEXT NOT NULL DEFAULT '')"
)

# Statuses worth restoring after a restart. A 'running' item never finished,
# so it comes back as 'pending'.
_RESTORE_AS_PENDING = ("pending", "running")


class QueueStore:
    """SQLite-backed durability for the batch queue."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path if db_path is not None else queue_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            self.db_path, timeout=_BUSY_TIMEOUT_MS / 1000)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def load_restorable(self) -> list[dict]:
        """Items to restore on startup, coerced to 'pending'.

        Items whose source file no longer exists are skipped so a restart
        does not resurrect work whose input has vanished.
        """
        cur = self._conn.execute(
            "SELECT id, path, name, status, priority FROM queue")
        out: list[dict] = []
        for (iid, path, name, status, priority) in cur.fetchall():
            if status not in _RESTORE_AS_PENDING:
                continue
            if not Path(path).is_file():
                continue
            out.append({
                "id": iid, "path": path, "name": name,
                "status": "pending", "priority": int(priority), "message": "",
            })
        return out

    def upsert(self, item: dict) -> None:
        self._conn.execute(
            "INSERT INTO queue (id, path, name, status, priority, message)"
            " VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET"
            "  path=excluded.path, name=excluded.name, status=excluded.status,"
            "  priority=excluded.priority, message=excluded.message",
            (item["id"], item["path"], item["name"], item["status"],
             int(item.get("priority", 0)), item.get("message", "")))
        self._conn.commit()

    def remove(self, item_id: str) -> None:
        self._conn.execute("DELETE FROM queue WHERE id = ?", (item_id,))
        self._conn.commit()

    def clear(self, status: str = "") -> None:
        if status:
            self._conn.execute("DELETE FROM queue WHERE status = ?", (status,))
        else:
            self._conn.execute("DELETE FROM queue")
        self._conn.commit()
