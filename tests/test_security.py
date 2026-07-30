"""Unit tests for core/security.py."""

import unittest
import tempfile
from pathlib import Path

from core.security import (
    sha256_hash,
    check_path_traversal,
    check_symlink_attacks,
    validate_file_size,
    build_sandbox_cmd,
    is_valid_package_name,
)
from config import ToolPaths


class TestSecurity(unittest.TestCase):

    def setUp(self):
        self.tmp_dir_obj = tempfile.TemporaryDirectory(prefix="pkgforge_test_")
        self.temp_dir = Path(self.tmp_dir_obj.name)

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_sha256_hash(self):
        test_file = self.temp_dir / "sample.txt"
        test_file.write_text("hello pkgforge", encoding="utf-8")
        digest = sha256_hash(test_file)
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)

    def test_validate_file_size(self):
        small_file = self.temp_dir / "small.deb"
        small_file.write_bytes(b"0" * 1024)
        warn = validate_file_size(small_file, max_mb=100, warn_mb=10)
        self.assertIsNone(warn)

        big_file = self.temp_dir / "big.deb"
        big_file.write_bytes(b"0" * (15 * 1024 * 1024))
        warn = validate_file_size(big_file, max_mb=100, warn_mb=10)
        self.assertIsNotNone(warn)
        self.assertIn("15 MB", warn)

        with self.assertRaises(ValueError):
            validate_file_size(big_file, max_mb=5, warn_mb=2)

    def test_check_path_traversal(self):
        safe_files = ["usr/bin/app", "usr/share/doc/README", "etc/app.conf"]
        self.assertEqual(check_path_traversal(safe_files), [])

        malicious_files = ["usr/bin/../../etc/shadow", "../var/log/syslog"]
        offending = check_path_traversal(malicious_files)
        self.assertEqual(len(offending), 2)

    def test_check_symlink_attacks(self):
        inside_target = self.temp_dir / "real_file.txt"
        inside_target.write_text("data")
        symlink_safe = self.temp_dir / "link_safe"
        symlink_safe.symlink_to(inside_target)

        outside_target = Path("/etc/passwd")
        symlink_unsafe = self.temp_dir / "link_unsafe"
        symlink_unsafe.symlink_to(outside_target)

        offending = check_symlink_attacks(self.temp_dir)
        self.assertEqual(len(offending), 1)
        self.assertIn("link_unsafe", offending[0])

    def test_build_sandbox_cmd(self):
        tools_no_bwrap = ToolPaths(bwrap="")
        prog, args = build_sandbox_cmd(["echo", "hello"], self.temp_dir, tools_no_bwrap)
        self.assertEqual(prog, "echo")
        self.assertEqual(args, ["hello"])

        tools_bwrap = ToolPaths(bwrap="/usr/bin/bwrap")
        prog, args = build_sandbox_cmd(["echo", "hello"], self.temp_dir, tools_bwrap)
        self.assertEqual(prog, "/usr/bin/bwrap")
        self.assertIn("--chdir", args)
        self.assertIn("echo", args)

    def test_is_valid_package_name(self):
        # Legitimate pacman package names
        for good in ("htop", "gtk3", "lib32-glibc", "python-pyqt6", "a.b_c+d@e"):
            self.assertTrue(is_valid_package_name(good), good)
        # Argument-injection / malformed names must be rejected
        for bad in ("", "-Rns", "--dbpath=/tmp", "a b", "a;rm -rf /", "$(reboot)", "x" * 200):
            self.assertFalse(is_valid_package_name(bad), bad)


if __name__ == "__main__":
    unittest.main()
