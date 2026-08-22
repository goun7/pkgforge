"""Tests for rpm_to_deb_converter guard paths.

Exercises graceful-degradation branches: missing file and tool availability.
"""

import shutil
import tempfile
import unittest
from pathlib import Path


class TestRpmToDebAvailability(unittest.TestCase):

    def test_matches_system(self):
        from core.rpm_to_deb_converter import is_rpm_to_deb_available
        expected = bool(shutil.which("rpm2cpio") and shutil.which("dpkg-deb"))
        self.assertEqual(is_rpm_to_deb_available(), expected)


class TestRpmToDebGuards(unittest.TestCase):

    def test_missing_file(self):
        from core.rpm_to_deb_converter import rpm_to_deb
        with tempfile.TemporaryDirectory() as td:
            ok, msg, out = rpm_to_deb(Path("/nonexistent/x.rpm"), Path(td))
            self.assertFalse(ok)
            self.assertIsNone(out)
            self.assertIn("bulunamad", msg)  # bulunamadı (not found)

    @unittest.skipIf(
        shutil.which("rpm2cpio") and shutil.which("dpkg-deb"),
        "both tools present — guard path not reachable",
    )
    def test_missing_tools_graceful(self):
        from core.rpm_to_deb_converter import rpm_to_deb
        with tempfile.TemporaryDirectory() as td:
            rpm = Path(td) / "fake.rpm"
            rpm.write_bytes(b"fake")
            ok, msg, out = rpm_to_deb(rpm, Path(td))
            self.assertFalse(ok)
            self.assertIsNone(out)
            # Must mention a missing tool, not crash
            self.assertTrue(msg)


if __name__ == "__main__":
    unittest.main()
