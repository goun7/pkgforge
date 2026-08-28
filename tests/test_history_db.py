"""Unit tests for core/history_db.py."""

import tempfile
import unittest
from pathlib import Path

from core.history_db import HistoryDB


class TestHistoryDB(unittest.TestCase):

    def setUp(self):
        self.tmp_dir_obj = tempfile.TemporaryDirectory(prefix="pkgforge_test_")
        self.temp_dir = Path(self.tmp_dir_obj.name)

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_history_db_crud(self):
        db_file = self.temp_dir / "test_history.db"
        db = HistoryDB(db_file)

        # Initial state should be empty
        history = db.get_history()
        self.assertEqual(len(history), 0)

        # Add record
        rec_id = db.add_record(
            package_name="demo-pkg",
            original_file="demo-pkg_1.0.0_amd64.deb",
            package_type="deb",
            sha256="abc123hash",
            status="success",
            output_pkg="/tmp/demo-pkg-1.0.0-1-x86_64.pkg.tar.zst",
            details="Success",
        )
        self.assertGreaterThan(rec_id, 0) if hasattr(self, "assertGreaterThan") else self.assertTrue(rec_id > 0)

        # Retrieve record
        records = db.get_history()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].package_name, "demo-pkg")
        self.assertEqual(records[0].sha256, "abc123hash")
        self.assertEqual(records[0].status, "success")

        # Clear history
        db.clear_history()
        self.assertEqual(len(db.get_history()), 0)

    def test_restore_records_undo(self):
        """Faz 9 (5.7): restore_records re-inserts records after a clear."""
        db_file = self.temp_dir / "restore_history.db"
        db = HistoryDB(db_file)

        db.add_record(
            package_name="pkg-a", original_file="a.deb", package_type="deb",
            sha256="h1", status="success", output_pkg="/tmp/a.pkg.tar.zst",
        )
        db.add_record(
            package_name="pkg-b", original_file="b.rpm", package_type="rpm",
            sha256="h2", status="installed", source_url="https://x/b.rpm",
        )
        snapshot = [r.__dict__ for r in db.get_history()]
        self.assertEqual(len(snapshot), 2)

        db.clear_history()
        self.assertEqual(len(db.get_history()), 0)

        restored = db.restore_records(snapshot)
        self.assertEqual(restored, 2)
        records = db.get_history()
        self.assertEqual(len(records), 2)
        names = {r.package_name for r in records}
        self.assertEqual(names, {"pkg-a", "pkg-b"})

    def test_restore_records_db_error_returns_zero(self):
        """Faz 9 (5.7): sqlite error during restore is swallowed, returns 0."""
        import sqlite3 as _sqlite3
        db_file = self.temp_dir / "restore_err.db"
        db = HistoryDB(db_file)
        # Drop the table externally to force an INSERT error on restore.
        ext = _sqlite3.connect(db_file)
        ext.execute("DROP TABLE conversions")
        ext.commit()
        ext.close()
        restored = db.restore_records([
            {"package_name": "x", "original_file": "o.deb", "package_type": "deb",
             "sha256": "h", "status": "success"},
        ])
        self.assertEqual(restored, 0)

    def test_restore_records_ignores_invalid_and_empty(self):
        """Faz 9 (5.7): non-dict entries are skipped; empty list restores 0."""
        db_file = self.temp_dir / "restore_invalid.db"
        db = HistoryDB(db_file)

        self.assertEqual(db.restore_records([]), 0)
        restored = db.restore_records([
            {"package_name": "ok", "original_file": "o.deb", "package_type": "deb",
             "sha256": "h", "status": "success"},
            "not-a-dict",
            None,
        ])
        self.assertEqual(restored, 1)
        self.assertEqual(len(db.get_history()), 1)


if __name__ == "__main__":
    unittest.main()
