"""Tests for HistoryDB (SQLite) and delta_updater graceful degradation.

HistoryDB is fully hermetic via a temp db_path. delta_updater tests cover
the xdelta3-missing graceful paths (xdelta3 is not installed in CI).
"""

import tempfile
import unittest
from pathlib import Path


class TestHistoryDB(unittest.TestCase):

    def _db(self, td):
        from core.history_db import HistoryDB
        return HistoryDB(db_path=Path(td) / "history.db")

    def test_add_and_get_history(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._db(td)
            rid = db.add_record(
                package_name="hello", original_file="hello.deb",
                package_type="deb", sha256="ab" * 32, status="success",
                output_pkg="hello-1.0.0-1-x86_64.pkg.tar.zst",
            )
            self.assertGreater(rid, 0)
            records = db.get_history()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].package_name, "hello")
            self.assertEqual(records[0].status, "success")

    def test_get_history_limit(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._db(td)
            for i in range(5):
                db.add_record(
                    package_name=f"pkg{i}", original_file="f.deb",
                    package_type="deb", sha256="x", status="success",
                )
            self.assertEqual(len(db.get_history(limit=3)), 3)

    def test_get_records_for_package(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._db(td)
            db.add_record(package_name="hello", original_file="a.deb",
                          package_type="deb", sha256="x", status="success")
            db.add_record(package_name="hello-git", original_file="b.deb",
                          package_type="deb", sha256="x", status="success")
            db.add_record(package_name="other", original_file="c.deb",
                          package_type="deb", sha256="x", status="success")
            # LIKE prefix match: hello matches hello and hello-git
            recs = db.get_records_for_package("hello")
            self.assertEqual(len(recs), 2)

    def test_clear_history(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._db(td)
            db.add_record(package_name="hello", original_file="a.deb",
                          package_type="deb", sha256="x", status="success")
            db.clear_history()
            self.assertEqual(db.get_history(), [])

    def test_update_http_headers(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._db(td)
            rid = db.add_record(package_name="hello", original_file="a.deb",
                                package_type="deb", sha256="x", status="success")
            db.update_http_headers(rid, etag="ETAG1", last_modified="LM1")
            recs = db.get_history()
            self.assertEqual(recs[0].http_etag, "ETAG1")
            self.assertEqual(recs[0].http_last_modified, "LM1")

    def test_usage_stats_empty(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._db(td)
            stats = db.get_usage_stats()
            self.assertEqual(stats["total"], 0)
            self.assertEqual(stats["by_status"], {})

    def test_usage_stats_counts(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._db(td)
            db.add_record(package_name="a", original_file="a.deb",
                          package_type="deb", sha256="x", status="success",
                          source_url="https://example.com/a.deb")
            db.add_record(package_name="b", original_file="b.rpm",
                          package_type="rpm", sha256="x", status="failed")
            stats = db.get_usage_stats()
            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["by_status"]["success"], 1)
            self.assertEqual(stats["by_status"]["failed"], 1)
            self.assertEqual(stats["by_type"]["deb"], 1)
            self.assertEqual(stats["by_type"]["rpm"], 1)
            self.assertEqual(stats["url_count"], 1)

    def test_backup_package_missing(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._db(td)
            self.assertIsNone(db.backup_package(Path(td) / "nope.pkg.tar.zst"))


class TestDeltaUpdaterGraceful(unittest.TestCase):

    def test_is_xdelta3_available_returns_bool(self):
        from core.delta_updater import is_xdelta3_available
        self.assertIsInstance(is_xdelta3_available(), bool)

    def test_create_delta_missing_files(self):
        from core.delta_updater import create_delta
        with tempfile.TemporaryDirectory() as td:
            # Even if xdelta3 were present, missing inputs must return False
            result = create_delta(
                Path(td) / "old", Path(td) / "new", Path(td) / "delta"
            )
            self.assertFalse(result)

    def test_apply_delta_missing_files(self):
        from core.delta_updater import apply_delta
        with tempfile.TemporaryDirectory() as td:
            result = apply_delta(
                Path(td) / "old", Path(td) / "delta", Path(td) / "out"
            )
            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
