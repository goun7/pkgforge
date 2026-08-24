"""Tests for core/security pure functions and filesystem-based checks.

Covers package-name validation, file-size limits, path traversal,
symlink escape detection, dangerous-file scanning, ELF heuristics,
and the bubblewrap sandbox command builder.
"""

import os
import tempfile
import unittest
from pathlib import Path

ELF_MAGIC = bytes([0x7f, 0x45, 0x4c, 0x46])


class TestIsValidPackageName(unittest.TestCase):

    def test_valid_names(self):
        from core.security import is_valid_package_name
        # pacman names cannot contain "/" — "@scope/pkg" is deliberately invalid
        for name in ("hello", "my-pkg", "libfoo2", "@scope", "a.b+c", "pkg_name"):
            self.assertTrue(is_valid_package_name(name), name)

    def test_rejects_slash(self):
        from core.security import is_valid_package_name
        self.assertFalse(is_valid_package_name("@scope/pkg"))
        self.assertFalse(is_valid_package_name("a/b"))

    def test_rejects_leading_dash(self):
        from core.security import is_valid_package_name
        self.assertFalse(is_valid_package_name("-Rns"))
        self.assertFalse(is_valid_package_name("--dbpath=/tmp"))

    def test_rejects_empty(self):
        from core.security import is_valid_package_name
        self.assertFalse(is_valid_package_name(""))

    def test_rejects_too_long(self):
        from core.security import is_valid_package_name
        self.assertFalse(is_valid_package_name("a" * 129))

    def test_rejects_shell_chars(self):
        from core.security import is_valid_package_name
        for bad in ("pkg;rm", "pkg name", "pkg$(x)", "pkg`x`", "pkg|x", "pkg&"):
            self.assertFalse(is_valid_package_name(bad), bad)


class TestValidateFileSize(unittest.TestCase):

    def test_small_file_ok(self):
        from core.security import validate_file_size
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 100)
            path = Path(f.name)
        try:
            self.assertIsNone(validate_file_size(path, max_mb=10, warn_mb=5))
        finally:
            path.unlink(missing_ok=True)

    def test_exceeds_max_raises(self):
        from core.security import validate_file_size
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * (2 * 1024 * 1024))  # 2 MB
            path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                validate_file_size(path, max_mb=1, warn_mb=1)
        finally:
            path.unlink(missing_ok=True)


class TestCheckPathTraversal(unittest.TestCase):

    def test_safe_paths(self):
        from core.security import check_path_traversal
        safe = ["usr/bin/hello", "./usr/share/doc/readme", "etc/config.conf"]
        self.assertEqual(check_path_traversal(safe), [])

    def test_dotdot_traversal(self):
        from core.security import check_path_traversal
        bad = ["../etc/passwd", "usr/../../etc/shadow", "foo/../../../x"]
        result = check_path_traversal(bad)
        self.assertEqual(len(result), 3)

    def test_absolute_escape(self):
        from core.security import check_path_traversal
        # /home and /root are not FHS roots -> flagged
        bad = ["/home/user/.ssh/id_rsa", "/root/.bashrc"]
        result = check_path_traversal(bad)
        self.assertEqual(len(result), 2)

    def test_absolute_fhs_ok(self):
        from core.security import check_path_traversal
        # /usr, /etc are FHS roots -> allowed
        ok = ["/usr/bin/app", "/etc/app.conf"]
        self.assertEqual(check_path_traversal(ok), [])


class TestSafeResolve(unittest.TestCase):

    def test_resolves_existing(self):
        from core.security import _safe_resolve
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub"
            p.mkdir()
            resolved = _safe_resolve(p)
            self.assertTrue(str(resolved).endswith("sub"))

    def test_missing_path_no_raise(self):
        from core.security import _safe_resolve
        # Must not raise even for nonexistent paths
        result = _safe_resolve(Path("/nonexistent/a/b/../c"))
        self.assertIsInstance(result, Path)


class TestCheckSymlinkAttacks(unittest.TestCase):

    def test_safe_relative_symlink(self):
        from core.security import check_symlink_attacks
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "real.txt").write_text("data")
            (root / "link.txt").symlink_to("real.txt")
            self.assertEqual(check_symlink_attacks(root), [])

    def test_fhs_absolute_symlink_safe(self):
        from core.security import check_symlink_attacks
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "usr").mkdir()
            (root / "usr" / "bin").mkdir()
            # FHS-style absolute target is considered safe
            (root / "usr" / "bin" / "app").symlink_to("/usr/share/app/bin/app")
            self.assertEqual(check_symlink_attacks(root), [])

    def test_escaping_relative_symlink_flagged(self):
        from core.security import check_symlink_attacks
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "pkg"
            root.mkdir()
            (root / "evil").symlink_to("../../etc/passwd")
            result = check_symlink_attacks(root)
            self.assertEqual(len(result), 1)

    def test_escaping_absolute_symlink_flagged(self):
        from core.security import check_symlink_attacks
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "pkg"
            root.mkdir()
            # /home is NOT an FHS root -> host-private escape -> flagged.
            # (Note: /etc, /usr etc. are deliberately treated as safe: FHS
            # absolute targets are interpreted relative to the package root
            # at install time — documented design in check_symlink_attacks.)
            (root / "evil").symlink_to("/home/user/.ssh/id_rsa")
            result = check_symlink_attacks(root)
            self.assertEqual(len(result), 1)

    def test_fhs_etc_symlink_is_safe_by_design(self):
        from core.security import check_symlink_attacks
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "pkg"
            root.mkdir()
            (root / "conf").symlink_to("/etc/app.conf")
            self.assertEqual(check_symlink_attacks(root), [])


class TestCheckDangerousFiles(unittest.TestCase):

    def test_clean_tree(self):
        from core.security import check_dangerous_files
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "normal.txt").write_text("hi")
            errors, warnings = check_dangerous_files(root)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_world_writable_warned(self):
        from core.security import check_dangerous_files
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = root / "writable.txt"
            f.write_text("hi")
            os.chmod(f, 0o666)
            errors, warnings = check_dangerous_files(root)
            self.assertEqual(errors, [])
            self.assertTrue(any("world-writable" in w for w in warnings))

    def test_setuid_warned(self):
        from core.security import check_dangerous_files
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = root / "suid.bin"
            f.write_bytes(b"\x7fELF" + b"\x00" * 10)
            os.chmod(f, 0o4755)
            errors, warnings = check_dangerous_files(root)
            self.assertEqual(errors, [])
            self.assertTrue(any("setuid" in w for w in warnings))

    def test_fifo_is_error(self):
        from core.security import check_dangerous_files
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            os.mkfifo(root / "pipe")
            errors, _warnings = check_dangerous_files(root)
            self.assertTrue(any("fifo" in e or "device" in e for e in errors))


class TestElfHeuristics(unittest.TestCase):

    def test_looks_like_elf(self):
        from core.security import _looks_like_elf
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(ELF_MAGIC + b"\x00" * 10)
            path = Path(f.name)
        try:
            self.assertTrue(_looks_like_elf(path))
        finally:
            path.unlink(missing_ok=True)

    def test_not_elf(self):
        from core.security import _looks_like_elf
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"#!/bin/sh")
            path = Path(f.name)
        try:
            self.assertFalse(_looks_like_elf(path))
        finally:
            path.unlink(missing_ok=True)

    def test_suspicious_pattern_detected(self):
        from core.security import _elf_has_suspicious_pattern
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(ELF_MAGIC + b"\x00" * 100 + b"/bin/sh -i" + b"\x00" * 10)
            path = Path(f.name)
        try:
            self.assertTrue(_elf_has_suspicious_pattern(path, 1 << 20))
        finally:
            path.unlink(missing_ok=True)

    def test_clean_elf_no_pattern(self):
        from core.security import _elf_has_suspicious_pattern
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(ELF_MAGIC + b"\x00" * 200)
            path = Path(f.name)
        try:
            self.assertFalse(_elf_has_suspicious_pattern(path, 1 << 20))
        finally:
            path.unlink(missing_ok=True)


class TestBuildSandboxCmd(unittest.TestCase):

    def test_no_bwrap_passthrough(self):
        from config import ToolPaths
        from core.security import build_sandbox_cmd
        # ToolPaths with no bwrap -> returns cmd unchanged
        tools = ToolPaths(bwrap="")
        prog, args = build_sandbox_cmd(["echo", "hi"], Path("/tmp"), tools)
        self.assertEqual(prog, "echo")
        self.assertEqual(args, ["hi"])

    def test_bwrap_wraps_command(self):
        from config import ToolPaths
        from core.security import build_sandbox_cmd
        with tempfile.TemporaryDirectory() as td:
            tools = ToolPaths(bwrap="/usr/bin/bwrap")
            prog, args = build_sandbox_cmd(["echo", "hi"], Path(td), tools)
            self.assertEqual(prog, "/usr/bin/bwrap")
            self.assertIn("--unshare-pid", args)
            self.assertIn("--unshare-net", args)  # network off by default
            self.assertEqual(args[-2:], ["echo", "hi"])

    def test_bwrap_allow_network(self):
        from config import ToolPaths
        from core.security import build_sandbox_cmd
        with tempfile.TemporaryDirectory() as td:
            tools = ToolPaths(bwrap="/usr/bin/bwrap")
            _prog, args = build_sandbox_cmd(
                ["echo", "hi"], Path(td), tools, allow_network=True
            )
            self.assertNotIn("--unshare-net", args)


if __name__ == "__main__":
    unittest.main()
