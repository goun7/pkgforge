"""Integration tests for core/cli_bridge.py — synchronous conversion wrappers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.cli_bridge import (
    ConversionResult,
)

try:
    from PyQt6.QtCore import QCoreApplication
    from core.cli_bridge import convert_deb_sync, convert_rpm_sync
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False


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


@unittest.skipUnless(HAS_PYQT6, "PyQt6 not installed")
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

    def test_ensure_qt_app_creates_app(self):
        """_ensure_qt_app should create a QCoreApplication."""
        from core.cli_bridge import _ensure_qt_app
        _ensure_qt_app()
        app = QCoreApplication.instance()
        self.assertIsNotNone(app)

    def test_ensure_qt_app_idempotent(self):
        """Calling _ensure_qt_app twice should not create a second app."""
        from core.cli_bridge import _ensure_qt_app
        _ensure_qt_app()
        first = id(QCoreApplication.instance())
        _ensure_qt_app()
        second = id(QCoreApplication.instance())
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
