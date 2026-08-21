"""PkgForge — SQLite Conversion & Installation History Database.

Persists package conversion logs, timestamps, hashes, source URLs, package backups,
and installation status for lifecycle tracking (uninstall & rollback).

Uses WAL journal mode for safe concurrent access from multiple PkgForge
instances.  A busy_timeout of 5 s avoids immediate ``SQLITE_BUSY`` errors
when two processes write at the same time.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import CONFIG_DIR

log = logging.getLogger(__name__)

DB_PATH = CONFIG_DIR / "history.db"
BACKUP_DIR = CONFIG_DIR / "backups"

# Busy-wait ceiling (ms) when another connection holds a write lock.
_BUSY_TIMEOUT_MS = 5_000


@dataclass
class HistoryRecord:
    """A record of a package conversion or installation event."""
    id: int
    timestamp: str
    package_name: str
    original_file: str
    package_type: str
    sha256: str
    status: str
    output_pkg: str
    details: str
    source_url: str = ""
    backup_pkg: str = ""
    http_etag: str = ""
    http_last_modified: str = ""


class HistoryDB:
    """Manages SQLite database for package conversion history and backup lifecycle."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=_BUSY_TIMEOUT_MS / 1000)
        conn.row_factory = sqlite3.Row
        # WAL mode: readers never block writers and vice-versa.
        # journal_mode is persistent per database file, but SET is cheap to
        # re-issue on every connection.
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        except sqlite3.Error:
            pass  # Older SQLite — fall back to default journal
        return conn

    def _init_db(self) -> None:
        """Create tables and apply schema migrations if needed."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        package_name TEXT NOT NULL,
                        original_file TEXT NOT NULL,
                        package_type TEXT NOT NULL,
                        sha256 TEXT NOT NULL,
                        status TEXT NOT NULL,
                        output_pkg TEXT DEFAULT '',
                        details TEXT DEFAULT '',
                        source_url TEXT DEFAULT '',
                        backup_pkg TEXT DEFAULT ''
                    )
                """)
                conn.commit()

                # Add missing columns if upgrading existing DB
                cursor = conn.execute("PRAGMA table_info(conversions)")
                columns = [row["name"] for row in cursor.fetchall()]
                if "source_url" not in columns:
                    conn.execute("ALTER TABLE conversions ADD COLUMN source_url TEXT DEFAULT ''")
                if "backup_pkg" not in columns:
                    conn.execute("ALTER TABLE conversions ADD COLUMN backup_pkg TEXT DEFAULT ''")
                if "http_etag" not in columns:
                    conn.execute("ALTER TABLE conversions ADD COLUMN http_etag TEXT DEFAULT ''")
                if "http_last_modified" not in columns:
                    conn.execute("ALTER TABLE conversions ADD COLUMN http_last_modified TEXT DEFAULT ''")
                conn.commit()
        except sqlite3.Error as exc:
            log.error("HistoryDB ilklendirme hatası: %s", exc)

    # ── Analytics helpers (used by usage dashboard) ─────────────

    def get_usage_stats(self) -> dict[str, Any]:
        """Return aggregated usage statistics from conversion history.

        Returns a dict with keys: total, by_status, by_type, by_arch,
        url_count, avg_output_size_mb, first_seen, last_seen.
        """
        stats: dict[str, Any] = {
            "total": 0,
            "by_status": {},
            "by_type": {},
            "by_arch": {},
            "url_count": 0,
            "avg_output_size_mb": 0.0,
            "first_seen": "",
            "last_seen": "",
        }
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT package_name, package_type, status, source_url,"
                    "       output_pkg, timestamp FROM conversions ORDER BY id"
                ).fetchall()
                if not rows:
                    return stats

                stats["total"] = len(rows)
                stats["first_seen"] = rows[0]["timestamp"]
                stats["last_seen"] = rows[-1]["timestamp"]

                total_size = 0.0
                size_count = 0
                for row in rows:
                    st = row["status"]
                    stats["by_status"][st] = stats["by_status"].get(st, 0) + 1
                    pt = row["package_type"]
                    stats["by_type"][pt] = stats["by_type"].get(pt, 0) + 1
                    if row["source_url"]:
                        stats["url_count"] += 1
                    # Output file size (if available)
                    out = row["output_pkg"]
                    if out:
                        try:
                            from pathlib import Path as _P
                            sz = _P(out).stat().st_size / (1024 * 1024)
                            total_size += sz
                            size_count += 1
                            # Infer arch from filename: …-x86_64.pkg.tar.zst
                            stem = _P(out).stem  # strip .zst
                            parts = stem.rsplit("-", 1)
                            if len(parts) == 2:
                                arch = parts[-1]  # e.g. x86_64
                                stats["by_arch"][arch] = stats["by_arch"].get(arch, 0) + 1
                        except OSError:
                            pass
                if size_count:
                    stats["avg_output_size_mb"] = round(total_size / size_count, 1)
        except sqlite3.Error as exc:
            log.warning("İstatistik hesaplama hatası: %s", exc)
        return stats

    def add_record(
        self,
        package_name: str,
        original_file: str,
        package_type: str,
        sha256: str,
        status: str,
        output_pkg: str = "",
        details: str = "",
        source_url: str = "",
        backup_pkg: str = "",
        http_etag: str = "",
        http_last_modified: str = "",
    ) -> int:
        """Add a new conversion/installation record."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO conversions
                    (package_name, original_file, package_type, sha256, status, output_pkg, details, source_url, backup_pkg, http_etag, http_last_modified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (package_name, original_file, package_type, sha256, status, output_pkg, details, source_url, backup_pkg, http_etag, http_last_modified),
                )
                conn.commit()
                log.info("Dönüşüm kaydı eklendi: %s (%s)", package_name, status)
                return cursor.lastrowid or 0
        except sqlite3.Error as exc:
            log.error("HistoryDB kayıt ekleme hatası: %s", exc)
            return 0

    def backup_package(self, pkg_path: Path) -> Path | None:
        """Backup a converted .pkg.tar.zst to ~/.config/pkgforge/backups/."""
        if not pkg_path.is_file():
            return None
        try:
            dest = BACKUP_DIR / pkg_path.name
            # Use streaming copy for files > 10MB to reduce memory usage
            if pkg_path.stat().st_size > 10 * 1024 * 1024:
                from core.streaming import stream_copy
                stream_copy(pkg_path, dest)
            else:
                shutil.copy2(pkg_path, dest)
            log.info("Yedek oluşturuldu: %s", dest.name)
            return dest
        except OSError as exc:
            log.warning("Yedekleme hatası: %s", exc)
            return None

    def get_history(self, limit: int = 50) -> list[HistoryRecord]:
        """Fetch recent conversion history records."""
        records: list[HistoryRecord] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, timestamp, package_name, original_file, package_type,
                           sha256, status, output_pkg, details, source_url, backup_pkg,
                           http_etag, http_last_modified
                    FROM conversions
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                for row in cursor.fetchall():
                    records.append(
                        HistoryRecord(
                            id=row["id"],
                            timestamp=row["timestamp"],
                            package_name=row["package_name"],
                            original_file=row["original_file"],
                            package_type=row["package_type"],
                            sha256=row["sha256"],
                            status=row["status"],
                            output_pkg=row["output_pkg"],
                            details=row["details"],
                            source_url=row["source_url"] if "source_url" in row.keys() else "",  # noqa: SIM118
                            backup_pkg=row["backup_pkg"] if "backup_pkg" in row.keys() else "",  # noqa: SIM118
                            http_etag=row["http_etag"] if "http_etag" in row.keys() else "",  # noqa: SIM118
                            http_last_modified=row["http_last_modified"] if "http_last_modified" in row.keys() else "",  # noqa: SIM118
                        )
                    )
        except sqlite3.Error as exc:
            log.error("HistoryDB okuma hatası: %s", exc)
        return records

    def get_records_for_package(self, package_name: str) -> list[HistoryRecord]:
        """Get all history records for a specific package name."""
        records: list[HistoryRecord] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, timestamp, package_name, original_file, package_type,
                           sha256, status, output_pkg, details, source_url, backup_pkg,
                           http_etag, http_last_modified
                    FROM conversions
                    WHERE package_name = ? OR package_name LIKE ?
                    ORDER BY id DESC
                    """,
                    (package_name, f"{package_name}%"),
                )
                for row in cursor.fetchall():
                    records.append(
                        HistoryRecord(
                            id=row["id"],
                            timestamp=row["timestamp"],
                            package_name=row["package_name"],
                            original_file=row["original_file"],
                            package_type=row["package_type"],
                            sha256=row["sha256"],
                            status=row["status"],
                            output_pkg=row["output_pkg"],
                            details=row["details"],
                            source_url=row["source_url"] if "source_url" in row.keys() else "",  # noqa: SIM118
                            backup_pkg=row["backup_pkg"] if "backup_pkg" in row.keys() else "",  # noqa: SIM118
                            http_etag=row["http_etag"] if "http_etag" in row.keys() else "",  # noqa: SIM118
                            http_last_modified=row["http_last_modified"] if "http_last_modified" in row.keys() else "",  # noqa: SIM118
                        )
                    )
        except sqlite3.Error as exc:
            log.error("HistoryDB paket arama hatası: %s", exc)
        return records

    def clear_history(self) -> None:
        """Clear all conversion history records."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM conversions")
                conn.commit()
                log.info("Dönüşüm geçmişi temizlendi")
        except sqlite3.Error as exc:
            log.error("HistoryDB temizleme hatası: %s", exc)

    def update_http_headers(self, record_id: int, etag: str, last_modified: str) -> None:
        """Update stored HTTP caching headers for a record (upstream tracker)."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE conversions SET http_etag = ?, http_last_modified = ? WHERE id = ?",
                    (etag, last_modified, record_id),
                )
                conn.commit()
        except sqlite3.Error as exc:
            log.warning("HTTP başlıkları güncellenemedi (id=%d): %s", record_id, exc)
