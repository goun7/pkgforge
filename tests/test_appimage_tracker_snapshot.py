"""Tests for appimage_converter, upstream_tracker offline, snapshot_manager.

All hermetic: temp files and offline mode only.
"""

import tempfile
import unittest
from pathlib import Path


class TestIsAppImageFile(unittest.TestCase):

    def test_appimage_magic(self):
        from core.appimage_converter import is_appimage_file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"AI\x02" + b"\x00" * 10)
            path = Path(f.name)
        try:
            self.assertTrue(is_appimage_file(path))
        finally:
            path.unlink(missing_ok=True)

    def test_not_appimage(self):
        from core.appimage_converter import is_appimage_file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"#!/bin/sh")
            path = Path(f.name)
        try:
            self.assertFalse(is_appimage_file(path))
        finally:
            path.unlink(missing_ok=True)

    def test_missing_file(self):
        from core.appimage_converter import is_appimage_file
        self.assertFalse(is_appimage_file(Path("/nonexistent/x.AppImage")))


class TestParseDesktopFile(unittest.TestCase):

    def test_parse(self):
        from core.appimage_converter import parse_desktop_file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("[Desktop Entry]\n")
            f.write("Name=MyApp\n")
            f.write("X-AppImage-Version=2.1\n")
            f.write("Comment=A test app\n")
            f.write("URL=https://example.com\n")
            path = Path(f.name)
        try:
            info = parse_desktop_file(path)
            self.assertEqual(info["Name"], "MyApp")
            self.assertEqual(info["X-AppImage-Version"], "2.1")
            self.assertEqual(info["Comment"], "A test app")
            self.assertEqual(info["URL"], "https://example.com")
            # Section headers must not be parsed as keys
            self.assertNotIn("[Desktop Entry]", info)
        finally:
            path.unlink(missing_ok=True)

    def test_missing_file(self):
        from core.appimage_converter import parse_desktop_file
        self.assertEqual(parse_desktop_file(Path("/nonexistent/x.desktop")), {})


class TestUpstreamTrackerOffline(unittest.TestCase):

    def _record(self):
        from core.history_db import HistoryRecord
        return HistoryRecord(
            id=1, timestamp="2026-01-01", package_name="hello",
            original_file="hello.deb", package_type="deb",
            sha256="ab", status="success", output_pkg="hello.pkg.tar.zst",
            details="", source_url="https://example.com/hello.deb",
        )

    def test_offline_skips_network(self):
        from core.upstream_tracker import check_upstream_update
        res = check_upstream_update(self._record(), offline=True)
        self.assertEqual(res.status, "offline")
        self.assertFalse(res.has_update)
        self.assertEqual(res.package_name, "hello")


class TestSnapshotManager(unittest.TestCase):

    def test_detect_backend_returns_known_value(self):
        from core.snapshot_manager import detect_backend
        self.assertIn(detect_backend(), ("btrfs", "zfs", "none"))

    def test_get_root_mount_point(self):
        from core.snapshot_manager import get_root_mount_point
        # On a real Linux system this returns a non-empty device path;
        # it must at least return a string without raising.
        result = get_root_mount_point()
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
