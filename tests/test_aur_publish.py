"""Tests for core/aur_publish.py — AUR publishing module."""

import tempfile
import unittest
from pathlib import Path

from core.aur_publish import (
    _extract_pkg_info,
    _generate_srcinfo,
    detect_build_system,
    _generate_pkgbuild,
)


class TestExtractPkgInfo(unittest.TestCase):
    """Test _extract_pkg_info function."""

    def test_extract_from_invalid_pkg(self):
        """Should handle invalid package gracefully."""
        with tempfile.NamedTemporaryFile(suffix=".pkg.tar.zst", delete=False) as f:
            pkg_path = Path(f.name)
            f.write(b"dummy")
        info = _extract_pkg_info(pkg_path)
        self.assertIsInstance(info, dict)
        pkg_path.unlink()


class TestDetectBuildSystem(unittest.TestCase):
    """Test detect_build_system function."""

    def test_detect_unknown_for_empty_dir(self):
        """Empty directory should return 'unknown'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = detect_build_system(Path(tmpdir))
            self.assertEqual(result, "unknown")

    def test_detect_cmake(self):
        """CMakeLists.txt should detect cmake."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "CMakeLists.txt").touch()
            result = detect_build_system(Path(tmpdir))
            self.assertEqual(result, "cmake")

    def test_detect_meson(self):
        """meson.build should detect meson."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "meson.build").touch()
            result = detect_build_system(Path(tmpdir))
            self.assertEqual(result, "meson")

    def test_detect_makefile(self):
        """Makefile should detect make."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Makefile").touch()
            result = detect_build_system(Path(tmpdir))
            self.assertEqual(result, "make")

    def test_detect_cargo(self):
        """Cargo.toml should detect cargo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Cargo.toml").touch()
            result = detect_build_system(Path(tmpdir))
            self.assertEqual(result, "cargo")

    def test_detect_python(self):
        """pyproject.toml should detect python."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pyproject.toml").touch()
            result = detect_build_system(Path(tmpdir))
            self.assertEqual(result, "python")


class TestGeneratePkgbuild(unittest.TestCase):
    """Test _generate_pkgbuild function."""

    def test_generate_make_pkgbuild(self):
        """Should generate valid PKGBUILD for make build system."""
        content = _generate_pkgbuild("test-pkg", "1.0.0", "https://example.com", "make")
        self.assertIn("pkgname=test-pkg", content)
        self.assertIn("pkgver=1.0.0", content)

    def test_generate_cmake_pkgbuild(self):
        """Should generate valid PKGBUILD for cmake build system."""
        content = _generate_pkgbuild("test-pkg", "1.0.0", "https://example.com", "cmake")
        self.assertIn("pkgname=test-pkg", content)
        self.assertIn("cmake", content.lower())

    def test_generate_cargo_pkgbuild(self):
        """Should generate valid PKGBUILD for cargo build system."""
        content = _generate_pkgbuild("test-pkg", "1.0.0", "https://example.com", "cargo")
        self.assertIn("pkgname=test-pkg", content)
        self.assertIn("cargo", content.lower())


class TestGenerateSrcinfo(unittest.TestCase):
    """Test _generate_srcinfo function."""

    def test_generate_from_invalid_path(self):
        """Should handle invalid directory gracefully."""
        try:
            result = _generate_srcinfo(Path("/nonexistent/PKGBUILD"))
            self.assertIsInstance(result, str)
        except (FileNotFoundError, OSError):
            # Expected when directory doesn't exist
            pass
