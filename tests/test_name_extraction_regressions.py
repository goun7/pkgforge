"""Regression tests: package-name extraction must not truncate dotted versions.

Covers the four call sites fixed to delegate to the authoritative
`config.extract_package_name` instead of `stem.split(".")[0]` /
`stem.split("-")[0]`, which mis-parsed names like `hello-1.0.0-1-any`
(-> "hello-1") and `my-cool-app-1.0.0-1.x86_64` (-> "my").
"""

import tempfile
import unittest
from pathlib import Path

from config import extract_package_name


class TestExtractPackageNameDotted(unittest.TestCase):
    """The authoritative extractor must survive dotted versions/arch."""

    def test_arch_dotted_version(self):
        self.assertEqual(
            extract_package_name("hello-1.0.0-1-x86_64.pkg.tar.zst"), "hello"
        )

    def test_arch_hyphenated_name(self):
        self.assertEqual(
            extract_package_name("my-cool-app-1.2.3-4-x86_64.pkg.tar.zst"),
            "my-cool-app",
        )

    def test_rpm_dot_arch(self):
        # RPM arch is dot-separated; must not leak into the name.
        self.assertEqual(
            extract_package_name("hello-1.0.0-1.x86_64.rpm"), "hello"
        )

    def test_rpm_hyphenated_dotted(self):
        self.assertEqual(
            extract_package_name("my-cool-app-2.0-3.x86_64.rpm"), "my-cool-app"
        )

    def test_deb_underscore(self):
        self.assertEqual(
            extract_package_name("hello_1.0.0-1_amd64.deb"), "hello"
        )

    def test_deb_dotted_name(self):
        # Debian names may contain dots (libssl1.1); keep them.
        self.assertEqual(
            extract_package_name("libssl1.1_1.1.1k-4_amd64.deb"), "libssl1.1"
        )


class TestSbomNameFallback(unittest.TestCase):
    """generate_sbom must use the clean name even without .PKGINFO."""

    def test_sbom_name_from_dotted_filename(self):
        from config import discover_tools
        from core.sbom import generate_sbom

        tools = discover_tools()
        with tempfile.TemporaryDirectory() as td:
            # Nonexistent file: _read_pkginfo returns {} so the name falls
            # back to extract_package_name. tar listing fails and returns
            # early, but package_name is already set.
            pkg = Path(td) / "hello-1.0.0-1-x86_64.pkg.tar.zst"
            sbom = generate_sbom(pkg, tools, include_hashes=False)
            self.assertEqual(sbom.package_name, "hello")


class TestAurPublishNameFallback(unittest.TestCase):
    """_extract_pkg_info filename fallback must not truncate dotted names."""

    def test_fallback_dotted_arch_pkg(self):
        from core.aur_publish import _extract_pkg_info

        with tempfile.TemporaryDirectory() as td:
            # < 4 hyphen segments forces the filename fallback branch.
            pkg = Path(td) / "hello-1.0.0.pkg.tar.zst"
            info = _extract_pkg_info(pkg)
            # Must NOT be the old buggy "hello-1" truncation.
            self.assertNotEqual(info["name"], "hello-1")

    def test_normal_arch_pkg_name(self):
        from core.aur_publish import _extract_pkg_info

        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "my-cool-app-1.2.3-4-x86_64.pkg.tar.zst"
            info = _extract_pkg_info(pkg)
            self.assertEqual(info["name"], "my-cool-app")


class TestRpmToDebNameFallback(unittest.TestCase):
    """rpm_to_deb filename fallback must keep hyphenated names intact."""

    def test_hyphenated_rpm_name_not_truncated(self):
        # The fallback inside convert() delegates to extract_package_name;
        # lock the behavior it relies on for hyphenated RPM names.
        self.assertEqual(
            extract_package_name("my-cool-app-2.0-3.x86_64.rpm"), "my-cool-app"
        )
        # The old stem.split("-")[0] would have returned just "my".
        self.assertNotEqual(
            extract_package_name("my-cool-app-2.0-3.x86_64.rpm"), "my"
        )


if __name__ == "__main__":
    unittest.main()
