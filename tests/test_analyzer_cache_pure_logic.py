"""Tests for package_analyzer parsers, aur_checker version compare, OfflineCache.

All hermetic: temp dirs and in-memory strings only.
"""

import json
import tempfile
import time
import unittest
from pathlib import Path


class TestParseDebControl(unittest.TestCase):

    def _meta(self):
        from core.package_analyzer import PackageMetadata
        return PackageMetadata()

    def test_basic_fields(self):
        from core.package_analyzer import _parse_deb_control
        meta = self._meta()
        text = (
            "Package: hello\n"
            "Version: 1.0.0-1\n"
            "Architecture: amd64\n"
            "Maintainer: Test <t@example.com>\n"
            "Homepage: https://example.com\n"
            "Description: Short line\n"
            " Long continuation line\n"
        )
        _parse_deb_control(text, meta)
        self.assertEqual(meta.name, "hello")
        self.assertEqual(meta.version, "1.0.0-1")
        self.assertEqual(meta.arch, "amd64")
        self.assertEqual(meta.maintainer, "Test <t@example.com>")
        self.assertEqual(meta.url, "https://example.com")
        self.assertEqual(meta.description, "Short line")

    def test_depends_split(self):
        from core.package_analyzer import _parse_deb_control
        meta = self._meta()
        _parse_deb_control("Depends: libc6 (>= 2.34), libm6, zlib1g\n", meta)
        self.assertEqual(meta.depends, ["libc6", "libm6", "zlib1g"])

    def test_conflicts_split(self):
        from core.package_analyzer import _parse_deb_control
        meta = self._meta()
        _parse_deb_control("Conflicts: old-hello, legacy-hello\n", meta)
        self.assertEqual(meta.conflicts, ["old-hello", "legacy-hello"])

    def test_installed_size(self):
        from core.package_analyzer import _parse_deb_control
        meta = self._meta()
        _parse_deb_control("Installed-Size: 1234\n", meta)
        self.assertEqual(meta.installed_size_kb, 1234)

    def test_installed_size_invalid(self):
        from core.package_analyzer import _parse_deb_control
        meta = self._meta()
        _parse_deb_control("Installed-Size: not-a-number\n", meta)
        self.assertEqual(meta.installed_size_kb, 0)

    def test_empty_control(self):
        from core.package_analyzer import _parse_deb_control
        meta = self._meta()
        _parse_deb_control("", meta)
        self.assertEqual(meta.name, "")

    def test_line_without_colon_ignored(self):
        from core.package_analyzer import _parse_deb_control
        meta = self._meta()
        _parse_deb_control("garbage line no colon\nPackage: x\n", meta)
        self.assertEqual(meta.name, "x")


class TestTarFlagsFor(unittest.TestCase):

    def test_gz(self):
        from core.package_analyzer import _tar_flags_for
        self.assertEqual(_tar_flags_for("data.tar.gz"), "z")

    def test_xz(self):
        from core.package_analyzer import _tar_flags_for
        self.assertEqual(_tar_flags_for("data.tar.xz"), "J")

    def test_bz2(self):
        from core.package_analyzer import _tar_flags_for
        self.assertEqual(_tar_flags_for("data.tar.bz2"), "j")

    def test_zst(self):
        from core.package_analyzer import _tar_flags_for
        self.assertEqual(_tar_flags_for("data.tar.zst"), "")

    def test_unknown(self):
        from core.package_analyzer import _tar_flags_for
        self.assertEqual(_tar_flags_for("data.tar.lzma"), "")


class TestParseRpmFilename(unittest.TestCase):

    def _meta(self):
        from core.package_analyzer import PackageMetadata
        return PackageMetadata()

    def test_standard_name(self):
        from core.package_analyzer import _parse_rpm_filename
        meta = self._meta()
        _parse_rpm_filename(Path("hello-1.0.0-1.x86_64.rpm"), meta)
        self.assertEqual(meta.name, "hello")
        self.assertEqual(meta.version, "1.0.0-1")
        self.assertEqual(meta.arch, "x86_64")

    def test_noarch(self):
        from core.package_analyzer import _parse_rpm_filename
        meta = self._meta()
        _parse_rpm_filename(Path("docs-2.5-3.noarch.rpm"), meta)
        self.assertEqual(meta.name, "docs")
        self.assertEqual(meta.arch, "noarch")

    def test_hyphenated_name(self):
        from core.package_analyzer import _parse_rpm_filename
        meta = self._meta()
        _parse_rpm_filename(Path("my-cool-app-1.2.3-4.x86_64.rpm"), meta)
        self.assertEqual(meta.name, "my-cool-app")
        self.assertEqual(meta.version, "1.2.3-4")

    def test_no_version_fallback(self):
        from core.package_analyzer import _parse_rpm_filename
        meta = self._meta()
        _parse_rpm_filename(Path("weirdpackage.rpm"), meta)
        self.assertEqual(meta.name, "weirdpackage")


class TestAurVersionCompare(unittest.TestCase):
    """aur_checker._version_compare — vercmp binary or Python fallback."""

    def test_greater(self):
        from core.aur_checker import _version_compare
        self.assertGreater(_version_compare("2.0-1", "1.9-1"), 0)

    def test_less(self):
        from core.aur_checker import _version_compare
        self.assertLess(_version_compare("1.0-1", "1.1-1"), 0)

    def test_equal(self):
        from core.aur_checker import _version_compare
        self.assertEqual(_version_compare("1.0-1", "1.0-1"), 0)

    def test_epoch_stripped_in_fallback(self):
        from core.aur_checker import _version_compare
        # Same upstream version, one with epoch — vercmp handles this; the
        # fallback strips epochs. Either way 1:1.0 > 1.0 must not be negative.
        self.assertGreaterEqual(_version_compare("1:1.0-1", "1.0-1"), 0)


class TestOfflineCache(unittest.TestCase):

    def _cache(self, td, ttl=3600):
        from core.offline_cache import OfflineCache
        return OfflineCache(cache_dir=Path(td), ttl=ttl)

    def test_put_get_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._cache(td)
            c.put("aur", "hello", {"version": "1.0"})
            self.assertEqual(c.get("aur", "hello"), {"version": "1.0"})

    def test_get_missing(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._cache(td)
            self.assertIsNone(c.get("aur", "nope"))

    def test_ttl_expiry(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._cache(td, ttl=0)  # expires immediately
            c.put("aur", "hello", {"v": 1})
            time.sleep(0.01)
            self.assertIsNone(c.get("aur", "hello"))

    def test_invalidate(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._cache(td)
            c.put("aur", "hello", {"v": 1})
            self.assertTrue(c.invalidate("aur", "hello"))
            self.assertIsNone(c.get("aur", "hello"))
            self.assertFalse(c.invalidate("aur", "hello"))

    def test_clear_namespace(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._cache(td)
            c.put("aur", "a", {"v": 1})
            c.put("aur", "b", {"v": 2})
            c.put("tracker", "c", {"v": 3})
            n = c.clear_namespace("aur")
            self.assertEqual(n, 2)
            self.assertIsNone(c.get("aur", "a"))
            self.assertEqual(c.get("tracker", "c"), {"v": 3})

    def test_clear_all(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._cache(td)
            c.put("aur", "a", {"v": 1})
            c.put("tracker", "c", {"v": 3})
            n = c.clear_all()
            self.assertEqual(n, 2)

    def test_stats(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._cache(td)
            c.put("aur", "a", {"v": 1})
            s = c.stats()
            self.assertIsInstance(s, dict)

    def test_corrupt_cache_file(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._cache(td)
            c.put("aur", "hello", {"v": 1})
            # Corrupt the underlying file
            path = c._key_path("aur", "hello")
            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(c.get("aur", "hello"))

    def test_get_or_fetch_uses_cache(self):
        with tempfile.TemporaryDirectory() as td:
            c = self._cache(td)
            calls = []
            def fetcher():
                calls.append(1)
                return {"v": 42}
            v1 = c.get_or_fetch("aur", "k", fetcher)
            v2 = c.get_or_fetch("aur", "k", fetcher)
            self.assertEqual(v1, {"v": 42})
            self.assertEqual(v2, {"v": 42})
            self.assertEqual(len(calls), 1)  # second call served from cache


if __name__ == "__main__":
    unittest.main()
