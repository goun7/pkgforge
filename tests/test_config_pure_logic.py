"""Tests for config.py pure functions: name extraction, tool discovery, temp dirs.

All hermetic: in-memory ToolPaths and temp dirs only.
"""

import tempfile
import unittest
from pathlib import Path


class TestExtractPackageName(unittest.TestCase):

    def test_deb_standard(self):
        from config import extract_package_name
        self.assertEqual(extract_package_name("hello_1.0.0-1_amd64.deb"), "hello")

    def test_deb_dotted_name(self):
        from config import extract_package_name
        self.assertEqual(extract_package_name("libssl1.1_1.1.0-1_amd64.deb"), "libssl1.1")

    def test_deb_hyphenated(self):
        from config import extract_package_name
        self.assertEqual(extract_package_name("python3-pip_21.0-1_all.deb"), "python3-pip")

    def test_rpm_standard(self):
        from config import extract_package_name
        self.assertEqual(extract_package_name("openssl-1.1.1k-4-x86_64.rpm"), "openssl")

    def test_rpm_noarch(self):
        from config import extract_package_name
        self.assertEqual(extract_package_name("hello-1.0.0-1.noarch.rpm"), "hello")

    def test_rpm_epoch(self):
        from config import extract_package_name
        self.assertEqual(extract_package_name("1:openssl-1.1.1k-4-x86_64.rpm"), "openssl")

    def test_rpm_hyphenated_name(self):
        from config import extract_package_name
        self.assertEqual(extract_package_name("my-cool-app-2.0-1-x86_64.rpm"), "my-cool-app")

    def test_arch_pkg(self):
        from config import extract_package_name
        self.assertEqual(
            extract_package_name("hello-1.0.0-1-x86_64.pkg.tar.zst"), "hello"
        )

    def test_url_basename(self):
        from config import extract_package_name
        self.assertEqual(
            extract_package_name("https://example.com/dl/hello_1.0.0-1_amd64.deb"),
            "hello",
        )


class TestToolPaths(unittest.TestCase):

    def test_missing_required_empty_when_all_set(self):
        from config import ToolPaths
        t = ToolPaths(
            pacman="/usr/bin/pacman", makepkg="/usr/bin/makepkg",
            fakeroot="/usr/bin/fakeroot", file_cmd="/usr/bin/file",
            pkexec="/usr/bin/pkexec", bsdtar="/usr/bin/bsdtar",
        )
        self.assertEqual(t.missing_required, [])

    def test_missing_required_lists_absent(self):
        from config import ToolPaths
        t = ToolPaths(pacman="/usr/bin/pacman")  # everything else empty
        missing = t.missing_required
        self.assertIn("makepkg", missing)
        self.assertIn("fakeroot", missing)
        self.assertNotIn("pacman", missing)

    def test_missing_optional(self):
        from config import ToolPaths
        t = ToolPaths(debtap="/usr/bin/debtap")
        missing = t.missing_optional
        self.assertIn("rpm2cpio", missing)
        self.assertNotIn("debtap", missing)

    def test_has_distrobox(self):
        from config import ToolPaths
        self.assertFalse(ToolPaths().has_distrobox)
        self.assertTrue(ToolPaths(distrobox="/usr/bin/distrobox").has_distrobox)


class TestDiscoverTools(unittest.TestCase):

    def test_returns_toolpaths(self):
        from config import ToolPaths, discover_tools
        t = discover_tools()
        self.assertIsInstance(t, ToolPaths)


class TestTempDirs(unittest.TestCase):

    def test_create_temp_dir_secure(self):
        from config import create_temp_dir
        d = create_temp_dir()
        try:
            self.assertTrue(d.is_dir())
            self.assertTrue(d.name.startswith("pkgforge_"))
            # Must be 700 (owner-only)
            mode = d.stat().st_mode & 0o777
            self.assertEqual(mode, 0o700)
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)

    def test_cleanup_orphaned(self):
        from config import cleanup_orphaned_temp_dirs, create_temp_dir
        d = create_temp_dir()
        self.assertTrue(d.is_dir())
        removed = cleanup_orphaned_temp_dirs()
        self.assertGreaterEqual(removed, 1)
        self.assertFalse(d.is_dir())


if __name__ == "__main__":
    unittest.main()
