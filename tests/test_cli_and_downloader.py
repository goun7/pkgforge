"""Unit tests for downloader, cli, native_deb_converter, upstream_tracker, and cross_check."""

import unittest
import tempfile
from pathlib import Path

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

    def test_cross_check_package(self):
        report = cross_check_package("htop", local_version="3.2.0")
        self.assertIsInstance(report.recommended_source, str)
        self.assertIn(report.recommended_source, ("local", "aur", "flatpak"))


if __name__ == "__main__":
    unittest.main()
