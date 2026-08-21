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


if __name__ == "__main__":
    unittest.main()
