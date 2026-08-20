"""Unit tests for core/security.py."""

import unittest
import tempfile
from pathlib import Path

from core.security import (
    sha256_hash,
    check_path_traversal,
    check_symlink_attacks,
    check_dangerous_files,
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

    def test_check_path_traversal_fhs_roots(self):
        # FHS roots (incl. lib32/run) must not be flagged as traversal.
        safe_files = [
            "usr/bin/app",
            "usr/share/doc/README",
            "lib32/libfoo.so",
            "run/qoder/qoder.sock",
            "etc/app.conf",
            "opt/vendor/bin/tool",
            "var/lib/app/data",
        ]
        self.assertEqual(check_path_traversal(safe_files), [])

    def test_check_dangerous_files(self):
        # setuid binary → warning (Electron chrome-sandbox is legitimately 4755)
        setuid_file = self.temp_dir / "usr" / "bin"
        setuid_file.mkdir(parents=True)
        suid = setuid_file / "helper"
        suid.write_bytes(b"x")
        suid.chmod(0o4755)

        # world-writable regular file → warning
        world_writable = self.temp_dir / "writable.conf"
        world_writable.write_bytes(b"y")
        world_writable.chmod(0o666)

        # world-writable directory → warning
        world_writable_dir = self.temp_dir / "writable_dir"
        world_writable_dir.mkdir()
        world_writable_dir.chmod(0o777)

        # clean file → nothing
        clean = self.temp_dir / "clean.txt"
        clean.write_bytes(b"z")
        clean.chmod(0o644)

        # FIFO node → error
        fifo = self.temp_dir / "pipe"
        try:
            import os as _os
            _os.mkfifo(fifo)
        except OSError:
            pass

        errors, warnings = check_dangerous_files(self.temp_dir)
        joined_warnings = "\n".join(warnings)
        self.assertIn("helper", joined_warnings)
        self.assertIn("writable.conf", joined_warnings)
        self.assertIn("writable_dir", joined_warnings)
        self.assertNotIn("clean.txt", joined_warnings)
        if fifo.exists() and not fifo.is_file():
            self.assertIn("pipe", "\n".join(errors))

    def test_check_dangerous_files_suspicious_elf(self):
        suspicious = self.temp_dir / "evil.bin"
        suspicious.write_bytes(b"\x7fELF" + b"\x00" * 64 + b"nc -e /bin/sh")
        errors, warnings = check_dangerous_files(self.temp_dir)
        self.assertIn("evil.bin", "\n".join(warnings))

    def test_check_symlink_attacks(self):
        inside_target = self.temp_dir / "real_file.txt"
        inside_target.write_text("data")
        symlink_safe = self.temp_dir / "link_safe"
        symlink_safe.symlink_to(inside_target)

        # FHS-style absolute symlink (e.g. /usr/bin/qoder -> /usr/share/qoder/bin/qoder)
        # resolves inside the package root at install time → must be allowed.
        usr_dir = self.temp_dir / "usr"
        usr_dir.mkdir()
        fhs_link = usr_dir / "qoder"
        fhs_link.symlink_to("/usr/share/qoder/bin/qoder")

        # Symlink escaping into host-private storage → must be flagged.
        outside_target = Path("/home/user/private-key")
        symlink_unsafe = self.temp_dir / "link_unsafe"
        symlink_unsafe.symlink_to(outside_target)

        # Relative symlink escaping via .. → must be flagged.
        nested = self.temp_dir / "a" / "b"
        nested.mkdir(parents=True)
        rel_escape = nested / "escape"
        rel_escape.symlink_to("../../../etc/passwd")

        offending = check_symlink_attacks(self.temp_dir)
        self.assertEqual(len(offending), 2, offending)
        joined = "\n".join(offending)
        self.assertIn("link_unsafe", joined)
        self.assertIn("escape", joined)
        # The legitimate FHS link and the inside link must not be flagged.
        self.assertNotIn("qoder", joined)
        self.assertNotIn("link_safe", joined)

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
