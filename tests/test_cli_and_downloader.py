"""Unit tests for downloader, cli, native_deb_converter, upstream_tracker, and cross_check."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.downloader import download_package
from core.upstream_tracker import check_upstream_update
from core.cross_check import cross_check_package
from core.history_db import HistoryRecord, HistoryDB


class TestRoadmapModules(unittest.TestCase):

    def setUp(self):
        self.tmp_dir_obj = tempfile.TemporaryDirectory(prefix="pkgforge_test_")
        self.temp_dir = Path(self.tmp_dir_obj.name)

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_downloader_invalid_scheme(self):
        with self.assertRaises(ValueError):
            download_package("ftp://example.com/pkg.deb", self.temp_dir)

    def test_downloader_rejects_http_by_default(self):
        # Plain http must be refused before any network access (HTTPS-only default)
        with self.assertRaises(ValueError):
            download_package("http://example.com/pkg.deb", self.temp_dir)

    def test_downloader_response_info_captures_headers(self):
        """response_info dict should receive ETag and Last-Modified from HTTP response."""
        mock_resp = MagicMock()
        mock_resp.headers = {
            "ETag": '"abc123"',
            "Last-Modified": "Tue, 01 Jan 2026 00:00:00 GMT",
            "Content-Length": "1024",
        }
        mock_resp.read.side_effect = [b"x" * 1024, b""]

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda s: s
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.headers = mock_resp.headers
        mock_ctx.read = mock_resp.read

        with patch("core.downloader.urllib.request.urlopen", return_value=mock_ctx):
            info: dict[str, str] = {}
            download_package("https://example.com/test.deb", self.temp_dir, response_info=info)

        self.assertEqual(info["etag"], "abc123")
        self.assertEqual(info["last_modified"], "Tue, 01 Jan 2026 00:00:00 GMT")
        self.assertEqual(info["content_length"], "1024")

    def test_downloader_response_info_not_required(self):
        """download_package works without response_info (backward compatible)."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda s: s
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.headers = {}
        mock_ctx.read.side_effect = [b"data", b""]

        with patch("core.downloader.urllib.request.urlopen", return_value=mock_ctx):
            # No response_info → should work fine
            path = download_package("https://example.com/test.deb", self.temp_dir)
            self.assertTrue(path.is_file())

    def test_upstream_tracker_no_url(self):
        rec = HistoryRecord(
            id=1,
            timestamp="2026-07-29",
            package_name="test-pkg",
            original_file="test.deb",
            package_type="deb",
            sha256="123",
            status="success",
            output_pkg="",
            details="",
            source_url="",
        )
        res = check_upstream_update(rec)
        self.assertFalse(res.has_update)
        self.assertEqual(res.status, "no_url")

    def test_upstream_tracker_etag_changed(self):
        """When stored ETag differs from current ETag, has_update should be True."""
        rec = HistoryRecord(
            id=1, timestamp="2026-08-01", package_name="test-pkg",
            original_file="test.deb", package_type="deb", sha256="abc",
            status="success", output_pkg="", details="",
            source_url="https://example.com/test.deb",
            http_etag="old-etag-value",
        )

        mock_resp = MagicMock()
        mock_resp.headers = {
            "ETag": '"new-etag-value"',
            "Last-Modified": "Tue, 19 Aug 2026 00:00:00 GMT",
        }
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda s: s
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.headers = mock_resp.headers

        with patch("core.upstream_tracker.urllib.request.urlopen", return_value=mock_ctx):
            res = check_upstream_update(rec)

        self.assertTrue(res.has_update)
        self.assertIn("ETag", res.detail)

    def test_upstream_tracker_last_modified_changed(self):
        """When Last-Modified differs and ETag matches, has_update should be True."""
        rec = HistoryRecord(
            id=2, timestamp="2026-08-01", package_name="test-pkg",
            original_file="test.deb", package_type="deb", sha256="abc",
            status="success", output_pkg="", details="",
            source_url="https://example.com/test.deb",
            http_etag="same-etag",
            http_last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
        )

        mock_resp = MagicMock()
        mock_resp.headers = {
            "ETag": '"same-etag"',
            "Last-Modified": "Tue, 19 Aug 2026 00:00:00 GMT",
        }
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda s: s
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.headers = mock_resp.headers

        with patch("core.upstream_tracker.urllib.request.urlopen", return_value=mock_ctx):
            res = check_upstream_update(rec)

        self.assertTrue(res.has_update)
        self.assertIn("Last-Modified", res.detail)

    def test_upstream_tracker_no_change(self):
        """When ETag and Last-Modified match stored values, has_update should be False."""
        rec = HistoryRecord(
            id=3, timestamp="2026-08-01", package_name="test-pkg",
            original_file="test.deb", package_type="deb", sha256="abc",
            status="success", output_pkg="", details="",
            source_url="https://example.com/test.deb",
            http_etag="same-etag",
            http_last_modified="same-date",
        )

        mock_resp = MagicMock()
        mock_resp.headers = {
            "ETag": '"same-etag"',
            "Last-Modified": "same-date",
        }
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda s: s
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.headers = mock_resp.headers

        with patch("core.upstream_tracker.urllib.request.urlopen", return_value=mock_ctx):
            res = check_upstream_update(rec)

        self.assertFalse(res.has_update)
        self.assertIn("Değişiklik tespit edilmedi", res.detail)

    def test_upstream_tracker_first_check(self):
        """First check (no stored headers) should not flag as update."""
        rec = HistoryRecord(
            id=4, timestamp="2026-08-01", package_name="test-pkg",
            original_file="test.deb", package_type="deb", sha256="abc",
            status="success", output_pkg="", details="",
            source_url="https://example.com/test.deb",
            # No http_etag or http_last_modified → first check
        )

        mock_resp = MagicMock()
        mock_resp.headers = {
            "ETag": '"some-etag"',
            "Last-Modified": "some-date",
        }
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda s: s
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.headers = mock_resp.headers

        with patch("core.upstream_tracker.urllib.request.urlopen", return_value=mock_ctx):
            res = check_upstream_update(rec)

        self.assertFalse(res.has_update)  # First check → not an update
        self.assertIn("İlk kontrol", res.detail)
        # Should return etag/last_modified for storage
        self.assertEqual(res.etag, "some-etag")
        self.assertEqual(res.last_modified, "some-date")

    def test_history_db_http_headers(self):
        """HistoryDB should store and retrieve http_etag and http_last_modified."""
        db = HistoryDB(db_path=self.temp_dir / "test.db")
        record_id = db.add_record(
            package_name="test-pkg",
            original_file="test.deb",
            package_type="deb",
            sha256="abc123",
            status="converted",
            http_etag="my-etag",
            http_last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
        )
        self.assertGreater(record_id, 0)

        records = db.get_history(limit=1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].http_etag, "my-etag")
        self.assertEqual(records[0].http_last_modified, "Mon, 01 Jan 2024 00:00:00 GMT")

    def test_history_db_update_http_headers(self):
        """update_http_headers should modify stored values."""
        db = HistoryDB(db_path=self.temp_dir / "test2.db")
        record_id = db.add_record(
            package_name="test-pkg",
            original_file="test.deb",
            package_type="deb",
            sha256="abc",
            status="converted",
            http_etag="old-etag",
            http_last_modified="old-date",
        )

        db.update_http_headers(record_id, "new-etag", "new-date")

        records = db.get_history(limit=1)
        self.assertEqual(records[0].http_etag, "new-etag")
        self.assertEqual(records[0].http_last_modified, "new-date")

    def test_cross_check_package(self):
        report = cross_check_package("htop", local_version="3.2.0")
        self.assertIsInstance(report.recommended_source, str)
        self.assertIn(report.recommended_source, ("local", "aur", "flatpak"))


if __name__ == "__main__":
    unittest.main()
