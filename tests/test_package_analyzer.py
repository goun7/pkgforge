"""Unit tests for core/package_analyzer.py."""

import unittest
from pathlib import Path

from core.package_analyzer import (
    PackageMetadata,
    _parse_deb_control,
    _parse_rpm_filename,
)


class TestPackageAnalyzer(unittest.TestCase):

    def test_parse_deb_control(self):
        control_text = """Package: htop
Version: 3.2.1-1
Architecture: amd64
Maintainer: John Doe <john@example.com>
Installed-Size: 1024
Depends: libc6 (>= 2.34), libncursesw6 (>= 6.2)
Description: Interactive process viewer
 An interactive process viewer for Unix systems.
"""
        meta = PackageMetadata()
        _parse_deb_control(control_text, meta)

        self.assertEqual(meta.name, "htop")
        self.assertEqual(meta.version, "3.2.1-1")
        self.assertEqual(meta.arch, "amd64")
        self.assertEqual(meta.installed_size_kb, 1024)
        self.assertEqual(len(meta.depends), 2)
        self.assertEqual(meta.depends[0], "libc6")
        self.assertEqual(meta.description, "Interactive process viewer")

    def test_parse_rpm_filename(self):
        meta = PackageMetadata()
        _parse_rpm_filename(Path("htop-3.2.1-1.x86_64.rpm"), meta)

        self.assertEqual(meta.name, "htop")
        self.assertEqual(meta.version, "3.2.1-1")
        self.assertEqual(meta.arch, "x86_64")


if __name__ == "__main__":
    unittest.main()
