"""Tests for pure-logic functions in low-coverage core modules.

Targets: compatibility_checker, dep_resolver, delta_updater, quality_score.
Only subprocess-free / tmp-dir-based paths are exercised here so the suite
stays fast and hermetic.
"""

import tempfile
import unittest
from pathlib import Path

ELF_MAGIC = bytes([0x7f, 0x45, 0x4c, 0x46])


class TestVersionGt(unittest.TestCase):
    """compatibility_checker._version_gt — simple numeric version compare."""

    def test_greater(self):
        from core.compatibility_checker import _version_gt
        self.assertTrue(_version_gt("2.39", "2.38"))
        self.assertTrue(_version_gt("2.40", "2.39"))
        self.assertTrue(_version_gt("10.0", "9.9"))

    def test_less(self):
        from core.compatibility_checker import _version_gt
        self.assertFalse(_version_gt("2.38", "2.39"))
        self.assertFalse(_version_gt("1.0", "2.0"))

    def test_equal(self):
        from core.compatibility_checker import _version_gt
        self.assertFalse(_version_gt("2.39", "2.39"))

    def test_longer_version_is_greater(self):
        from core.compatibility_checker import _version_gt
        # 2.39.1 > 2.39 (extra component)
        self.assertTrue(_version_gt("2.39.1", "2.39"))
        self.assertFalse(_version_gt("2.39", "2.39.1"))


class TestParseDepString(unittest.TestCase):
    """dep_resolver._parse_dep_string — split name from version constraint."""

    def test_ge(self):
        from core.dep_resolver import _parse_dep_string
        self.assertEqual(_parse_dep_string("foo>=2.0"), ("foo", ">=2.0"))

    def test_le(self):
        from core.dep_resolver import _parse_dep_string
        self.assertEqual(_parse_dep_string("bar<=1.5"), ("bar", "<=1.5"))

    def test_gt(self):
        from core.dep_resolver import _parse_dep_string
        self.assertEqual(_parse_dep_string("baz>3"), ("baz", ">3"))

    def test_lt(self):
        from core.dep_resolver import _parse_dep_string
        self.assertEqual(_parse_dep_string("qux<4"), ("qux", "<4"))

    def test_eq(self):
        from core.dep_resolver import _parse_dep_string
        self.assertEqual(_parse_dep_string("exact=1.0"), ("exact", "=1.0"))

    def test_no_operator(self):
        from core.dep_resolver import _parse_dep_string
        self.assertEqual(_parse_dep_string("plaindep"), ("plaindep", ""))

    def test_whitespace(self):
        from core.dep_resolver import _parse_dep_string
        self.assertEqual(_parse_dep_string("  foo >= 2.0  "), ("foo", ">=2.0"))

    def test_empty(self):
        from core.dep_resolver import _parse_dep_string
        self.assertEqual(_parse_dep_string(""), ("", ""))


class TestParseSonames(unittest.TestCase):
    """dep_resolver soname parsers — regex extraction from tool output."""

    def test_readelf_needed(self):
        from core.dep_resolver import parse_needed_sonames
        out = (
            " 0x0000000000000001 (NEEDED)  Shared library: [libc.so.6]\n"
            " 0x0000000000000001 (NEEDED)  Shared library: [libm.so.6]\n"
            " 0x000000000000000e (SONAME)  Library soname: [libfoo.so.1]\n"
        )
        self.assertEqual(parse_needed_sonames(out), ["libc.so.6", "libm.so.6"])

    def test_readelf_empty(self):
        from core.dep_resolver import parse_needed_sonames
        self.assertEqual(parse_needed_sonames(""), [])

    def test_objdump_needed(self):
        from core.dep_resolver import parse_objdump_sonames
        out = (
            "  NEEDED               libc.so.6\n"
            "  NEEDED               libpthread.so.0\n"
            "  SONAME               libfoo.so.1\n"
        )
        self.assertEqual(
            parse_objdump_sonames(out), ["libc.so.6", "libpthread.so.0"]
        )

    def test_objdump_empty(self):
        from core.dep_resolver import parse_objdump_sonames
        self.assertEqual(parse_objdump_sonames(""), [])


class TestIsElfFile(unittest.TestCase):
    """dep_resolver.is_elf_file — ELF magic-byte detection."""

    def test_elf_magic(self):
        from core.dep_resolver import is_elf_file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(ELF_MAGIC + b"\x02\x01\x01\x00")
            path = Path(f.name)
        try:
            self.assertTrue(is_elf_file(path))
        finally:
            path.unlink(missing_ok=True)

    def test_not_elf(self):
        from core.dep_resolver import is_elf_file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"#!/bin/sh\necho hi\n")
            path = Path(f.name)
        try:
            self.assertFalse(is_elf_file(path))
        finally:
            path.unlink(missing_ok=True)

    def test_missing_file(self):
        from core.dep_resolver import is_elf_file
        self.assertFalse(is_elf_file(Path("/nonexistent/nope.bin")))

    def test_short_file(self):
        from core.dep_resolver import is_elf_file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"\x7fE")  # only 2 bytes
            path = Path(f.name)
        try:
            self.assertFalse(is_elf_file(path))
        finally:
            path.unlink(missing_ok=True)


class TestFindLocalPrevious(unittest.TestCase):
    """delta_updater.find_local_previous — locate prior package version."""

    def test_finds_matching_package(self):
        from core.delta_updater import find_local_previous
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "hello-1.0.0-1-x86_64.pkg.tar.zst").write_bytes(b"x")
            found = find_local_previous("hello", pkg_dir=d)
            self.assertIsNotNone(found)
            self.assertIn("hello", found.name)

    def test_ignores_sidecars(self):
        from core.delta_updater import find_local_previous
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "hello-1.0.0-1-x86_64.pkg.tar.zst.sig").write_bytes(b"x")
            (d / "hello-1.0.0-1-x86_64.pkg.tar.zst.provenance.json").write_bytes(b"{}")
            found = find_local_previous("hello", pkg_dir=d)
            self.assertIsNone(found)

    def test_no_match(self):
        from core.delta_updater import find_local_previous
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "other-2.0-1-x86_64.pkg.tar.zst").write_bytes(b"x")
            found = find_local_previous("hello", pkg_dir=d)
            self.assertIsNone(found)

    def test_missing_dir(self):
        from core.delta_updater import find_local_previous
        found = find_local_previous("hello", pkg_dir=Path("/nonexistent/dir"))
        self.assertIsNone(found)

    def test_picks_most_recent(self):
        import time

        from core.delta_updater import find_local_previous
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            old = d / "hello-0.9-1-x86_64.pkg.tar.zst"
            new = d / "hello-1.0-1-x86_64.pkg.tar.zst"
            old.write_bytes(b"old")
            time.sleep(0.01)
            new.write_bytes(b"new")
            found = find_local_previous("hello", pkg_dir=d)
            self.assertEqual(found.name, "hello-1.0-1-x86_64.pkg.tar.zst")

    def test_hyphenated_name_matches_exactly(self):
        """Regression: split("-")[0] truncated my-cool-app -> "my" and the
        substring check over-matched. Full-name comparison is required."""
        from core.delta_updater import find_local_previous
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "my-cool-app-1.0-1-x86_64.pkg.tar.zst").write_bytes(b"x")
            # Exact hyphenated name must match.
            found = find_local_previous("my-cool-app", pkg_dir=d)
            self.assertIsNotNone(found)
            self.assertEqual(found.name, "my-cool-app-1.0-1-x86_64.pkg.tar.zst")

    def test_prefix_does_not_over_match(self):
        """Searching for "my" must NOT match my-cool-app (old substring bug)."""
        from core.delta_updater import find_local_previous
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "my-cool-app-1.0-1-x86_64.pkg.tar.zst").write_bytes(b"x")
            found = find_local_previous("my", pkg_dir=d)
            self.assertIsNone(found)

    def test_dotted_version_name_matches(self):
        """Dotted versions must still resolve to the clean base name."""
        from core.delta_updater import find_local_previous
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "hello-1.0.0-1-x86_64.pkg.tar.zst").write_bytes(b"x")
            found = find_local_previous("hello", pkg_dir=d)
            self.assertIsNotNone(found)


class TestCompatibilityReportProps(unittest.TestCase):
    """CompatibilityReport.overall / grade / errors / warnings / passed."""

    def _report(self, severities):
        from core.compatibility_checker import (
            CheckResult,
            CheckSeverity,
            CompatibilityReport,
        )
        checks = [
            CheckResult(name=f"c{i}", severity=s, message="m")
            for i, s in enumerate(severities)
        ]
        return CompatibilityReport(checks=checks), CheckSeverity

    def test_overall_pass(self):
        from core.compatibility_checker import CheckSeverity
        rep, _ = self._report([CheckSeverity.PASS, CheckSeverity.PASS])
        self.assertEqual(rep.overall, CheckSeverity.PASS)

    def test_overall_warning(self):
        from core.compatibility_checker import CheckSeverity
        rep, _ = self._report([CheckSeverity.PASS, CheckSeverity.WARNING])
        self.assertEqual(rep.overall, CheckSeverity.WARNING)

    def test_overall_error(self):
        from core.compatibility_checker import CheckSeverity
        rep, _ = self._report([CheckSeverity.WARNING, CheckSeverity.ERROR])
        self.assertEqual(rep.overall, CheckSeverity.ERROR)

    def test_grade_a(self):
        from core.compatibility_checker import CheckSeverity
        rep, _ = self._report([CheckSeverity.PASS])
        self.assertEqual(rep.grade, "A")

    def test_grade_b(self):
        from core.compatibility_checker import CheckSeverity
        rep, _ = self._report([CheckSeverity.WARNING])
        self.assertEqual(rep.grade, "B")

    def test_grade_c(self):
        from core.compatibility_checker import CheckSeverity
        rep, _ = self._report([CheckSeverity.WARNING] * 3)
        self.assertEqual(rep.grade, "C")

    def test_grade_d(self):
        from core.compatibility_checker import CheckSeverity
        rep, _ = self._report([CheckSeverity.ERROR])
        self.assertEqual(rep.grade, "D")

    def test_grade_f(self):
        from core.compatibility_checker import CheckSeverity
        rep, _ = self._report([CheckSeverity.ERROR, CheckSeverity.ERROR])
        self.assertEqual(rep.grade, "F")

    def test_partitions(self):
        from core.compatibility_checker import CheckSeverity
        rep, _ = self._report([
            CheckSeverity.PASS, CheckSeverity.WARNING, CheckSeverity.ERROR,
        ])
        self.assertEqual(len(rep.passed), 1)
        self.assertEqual(len(rep.warnings), 1)
        self.assertEqual(len(rep.errors), 1)


if __name__ == "__main__":
    unittest.main()
