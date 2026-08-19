"""PkgForge — SQLite Conversion & Installation History Database.

Persists package conversion logs, timestamps, hashes, source URLs, package backups,
and installation status for lifecycle tracking (uninstall & rollback).
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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
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
                            source_url=row["source_url"] if "source_url" in row.keys() else "",
                            backup_pkg=row["backup_pkg"] if "backup_pkg" in row.keys() else "",
                            http_etag=row["http_etag"] if "http_etag" in row.keys() else "",
                            http_last_modified=row["http_last_modified"] if "http_last_modified" in row.keys() else "",
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
                            source_url=row["source_url"] if "source_url" in row.keys() else "",
                            backup_pkg=row["backup_pkg"] if "backup_pkg" in row.keys() else "",
                            http_etag=row["http_etag"] if "http_etag" in row.keys() else "",
                            http_last_modified=row["http_last_modified"] if "http_last_modified" in row.keys() else "",
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
