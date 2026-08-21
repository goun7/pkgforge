"""Integration tests for core/cli_bridge.py — synchronous conversion wrappers."""

import unittest
from pathlib import Path

from core.cli_bridge import (
    ConversionResult,
)

try:
    from core.cli_bridge import convert_deb_sync, convert_rpm_sync
    HAS_BRIDGE = True
except ImportError:
    HAS_BRIDGE = False


class TestConversionResult(unittest.TestCase):

    def test_defaults(self):
        r = ConversionResult()
        self.assertFalse(r.success)
        self.assertEqual(r.message, "")
        self.assertIsNone(r.output_pkg)

    def test_slots(self):
        r = ConversionResult()
        with self.assertRaises(AttributeError):
            r.nonexistent = True  # type: ignore


@unittest.skipUnless(HAS_BRIDGE, "cli_bridge converters unavailable")
class TestCliBridge(unittest.TestCase):

    def test_convert_deb_sync_no_file(self):
        """convert_deb_sync with nonexistent file should fail gracefully."""
        result = convert_deb_sync(
            Path("/nonexistent/file.deb"),
            Path("/tmp/output"),
        )
        self.assertFalse(result.success)

    def test_convert_rpm_sync_no_file(self):
        """convert_rpm_sync with nonexistent file should fail gracefully."""
        result = convert_rpm_sync(
            Path("/nonexistent/file.rpm"),
            Path("/tmp/output"),
        )
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
