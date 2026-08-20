"""Tests for converter plugins: flatpak, appimage, oci, from_source."""

import tempfile
import unittest
from pathlib import Path

from config import ToolPaths


class TestFlatpakConverter(unittest.TestCase):
    """Test flatpak_converter module."""

    def test_import(self):
        """Module should import without errors."""
        from core import flatpak_converter
        self.assertTrue(hasattr(flatpak_converter, "list_installed_apps"))

    def test_flatpak_list(self):
        """Should list installed Flatpak apps (or handle gracefully)."""
        from core.flatpak_converter import list_installed_apps
        result = list_installed_apps()
        self.assertIsInstance(result, list)

    def test_is_available(self):
        """Should report flatpak availability."""
        from core.flatpak_converter import is_flatpak_available
        result = is_flatpak_available()
        self.assertIsInstance(result, bool)


class TestAppImageConverter(unittest.TestCase):
    """Test appimage_converter module."""

    def test_import(self):
        """Module should import without errors."""
        from core import appimage_converter
        self.assertTrue(hasattr(appimage_converter, "is_appimage_available"))

    def test_is_appimage_file_nonexistent(self):
        """Non-existent file should return False."""
        from core.appimage_converter import is_appimage_file
        self.assertFalse(is_appimage_file(Path("/nonexistent/file.AppImage")))

    def test_is_appimage_file_regular(self):
        """Regular .deb file should return False."""
        from core.appimage_converter import is_appimage_file
        with tempfile.NamedTemporaryFile(suffix=".deb") as f:
            f.write(b"not an AppImage")
            f.flush()
            self.assertFalse(is_appimage_file(Path(f.name)))

    def test_is_available(self):
        """Should report AppImage availability."""
        from core.appimage_converter import is_appimage_available
        result = is_appimage_available()
        self.assertIsInstance(result, bool)


class TestOciBuilder(unittest.TestCase):
    """Test oci_builder module."""

    def test_import(self):
        """Module should import without errors."""
        from core import oci_builder
        self.assertTrue(hasattr(oci_builder, "build_oci_image"))

    def test_is_available(self):
        """Should report container runtime availability."""
        from core.oci_builder import is_container_runtime_available
        result = is_container_runtime_available()
        self.assertIsInstance(result, bool)


class TestFromSource(unittest.TestCase):
    """Test from_source module."""

    def test_import(self):
        """Module should import without errors."""
        from core import from_source
        self.assertTrue(hasattr(from_source, "generate_pkgbuild_from_source"))

    def test_version_detection_empty_dir(self):
        """Should return None for empty directory."""
        from core.from_source import _extract_version_from_file
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _extract_version_from_file(Path(tmpdir))
            self.assertIsNone(result)
