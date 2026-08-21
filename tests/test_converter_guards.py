"""Tests for converter guard paths (missing file / missing tool).

These exercise the early-return branches of the Qt-based converters,
which emit finished() synchronously without needing an event loop."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import ToolPaths


class TestRpmToDebConverter(unittest.TestCase):

    def test_is_available_returns_bool(self):
        from core.rpm_to_deb_converter import is_rpm_to_deb_available
        self.assertIsInstance(is_rpm_to_deb_available(), bool)

    def test_rpm_to_deb_missing_file(self):
        from core.rpm_to_deb_converter import rpm_to_deb
        with tempfile.TemporaryDirectory() as td:
            ok, msg, _path = rpm_to_deb(Path("/nonexistent.rpm"), Path(td))
            self.assertFalse(ok)
            self.assertIn("bulunamadı", msg)
            self.assertIsNone(_path)

    def test_rpm_to_deb_no_rpm2cpio(self):
        from core.rpm_to_deb_converter import rpm_to_deb
        with tempfile.TemporaryDirectory() as td:
            rpm = Path(td) / "test.rpm"
            rpm.write_bytes(b"fake")
            with patch("core.rpm_to_deb_converter.shutil.which", return_value=None):
                ok, msg, path = rpm_to_deb(rpm, Path(td))
                self.assertFalse(ok)
                self.assertIn("rpm2cpio", msg)


class TestNativeDebConverterGuards(unittest.TestCase):

    def test_convert_missing_file(self):
        from core.native_deb_converter import NativeDebConverter
        results = []
        conv = NativeDebConverter(ToolPaths())
        conv.finished.connect(lambda ok, msg, pkg: results.append((ok, msg)))
        conv.convert(Path("/nonexistent.deb"), Path("/tmp"))
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])
        self.assertIn("bulunamadı", results[0][1])

    def test_convert_no_makepkg(self):
        from core.native_deb_converter import NativeDebConverter
        results = []
        # ToolPaths() defaults every field to "" → makepkg missing.
        conv = NativeDebConverter(ToolPaths())
        conv.finished.connect(lambda ok, msg, pkg: results.append((ok, msg)))
        with tempfile.NamedTemporaryFile(suffix=".deb") as f:
            conv.convert(Path(f.name), Path("/tmp"))
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])
        self.assertIn("makepkg", results[0][1])

    def test_cancel(self):
        from core.native_deb_converter import NativeDebConverter
        conv = NativeDebConverter(ToolPaths())
        conv.cancel()  # should not raise


class TestDebConverterGuards(unittest.TestCase):

    def test_convert_no_debtap(self):
        from core.deb_converter import DebConverter
        results = []
        # ToolPaths() defaults every field to "" → debtap missing.
        conv = DebConverter(ToolPaths())
        conv.finished.connect(lambda ok, msg, pkg: results.append((ok, msg)))
        conv.convert(Path("/some.deb"), Path("/tmp"))
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])
        self.assertIn("debtap", results[0][1])

    def test_cancel(self):
        from core.deb_converter import DebConverter
        conv = DebConverter(ToolPaths())
        conv.cancel()  # should not raise


class TestDistroboxFallback(unittest.TestCase):

    def test_is_available(self):
        from core.distrobox_fallback import DistroboxFallback
        tools = ToolPaths()
        result = DistroboxFallback.is_available(tools)
        self.assertIsInstance(result, bool)


class TestInstallerGuards(unittest.TestCase):

    def test_install_missing_file(self):
        from core.installer import Installer
        results = []
        inst = Installer(ToolPaths())
        inst.finished.connect(lambda ok, msg: results.append((ok, msg)))
        inst.install(Path("/nonexistent.pkg.tar.zst"), "test")
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])
        self.assertIn("bulunamadı", results[0][1])

    def test_install_no_pkexec(self):
        from core.installer import Installer
        results = []
        # ToolPaths() defaults pkexec to "" → missing.
        inst = Installer(ToolPaths())
        inst.finished.connect(lambda ok, msg: results.append((ok, msg)))
        with tempfile.NamedTemporaryFile(suffix=".pkg.tar.zst") as f:
            inst.install(Path(f.name), "test")
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])
        self.assertIn("pkexec", results[0][1])

    def test_install_invalid_extension(self):
        from core.installer import Installer
        results = []
        tools = ToolPaths(pkexec="/usr/bin/pkexec")
        inst = Installer(tools)
        inst.finished.connect(lambda ok, msg: results.append((ok, msg)))
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            inst.install(Path(f.name), "test")
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])
        self.assertIn("Geçersiz", results[0][1])

    def test_find_install_helper_returns_path(self):
        from core.installer import _find_install_helper
        helper = _find_install_helper()
        self.assertIsInstance(helper, Path)


if __name__ == "__main__":
    unittest.main()
