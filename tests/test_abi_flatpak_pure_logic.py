"""Tests for abi_scanner report dataclasses and flatpak size estimator.

All hermetic: in-memory dataclasses and temp dirs only.
"""

import tempfile
import unittest
from pathlib import Path

ELF_MAGIC = bytes([0x7f, 0x45, 0x4c, 0x46])


class TestABIScanReport(unittest.TestCase):

    def test_empty_report_passes(self):
        from core.abi_scanner import ABIScanReport
        r = ABIScanReport()
        self.assertTrue(r.passed)
        self.assertEqual(r.error_count, 0)

    def test_mismatch_fails(self):
        from core.abi_scanner import ABIScanReport, SymbolMismatch
        r = ABIScanReport(mismatches=[
            SymbolMismatch(binary="bin/app", symbol="memcpy",
                           required_version="GLIBC_2.34",
                           available_version="GLIBC_2.33",
                           library="libc.so.6")
        ])
        self.assertFalse(r.passed)
        self.assertEqual(r.error_count, 1)

    def test_missing_lib_fails(self):
        from core.abi_scanner import ABIScanReport
        r = ABIScanReport(missing_libs=[("bin/app", "libfoo.so.1")])
        self.assertFalse(r.passed)
        self.assertEqual(r.error_count, 1)

    def test_namcap_error_fails(self):
        from core.abi_scanner import ABIScanReport, NamcapResult
        r = ABIScanReport(namcap_results=[
            NamcapResult(severity="error", tag="bad", message="bad thing")
        ])
        self.assertFalse(r.passed)
        self.assertEqual(r.error_count, 1)

    def test_namcap_warning_passes(self):
        from core.abi_scanner import ABIScanReport, NamcapResult
        r = ABIScanReport(namcap_results=[
            NamcapResult(severity="warning", tag="warn", message="minor")
        ])
        self.assertTrue(r.passed)  # warnings do not fail the report
        self.assertEqual(r.error_count, 0)

    def test_summary_contains_counts(self):
        from core.abi_scanner import ABIScanReport
        r = ABIScanReport(binary_count=5, checked_symbols=100)
        s = r.summary()
        self.assertIn("5", s)
        self.assertIn("100", s)

    def test_summary_lists_mismatches(self):
        from core.abi_scanner import ABIScanReport, SymbolMismatch
        r = ABIScanReport(mismatches=[
            SymbolMismatch(binary="bin/app", symbol="memcpy",
                           required_version="GLIBC_2.34",
                           available_version="GLIBC_2.33",
                           library="libc.so.6")
        ])
        s = r.summary()
        self.assertIn("memcpy", s)
        self.assertIn("GLIBC_2.34", s)


class TestIsElfBinary(unittest.TestCase):

    def test_elf(self):
        from core.abi_scanner import _is_elf_binary
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(ELF_MAGIC + b"\x00" * 10)
            path = Path(f.name)
        try:
            self.assertTrue(_is_elf_binary(path))
        finally:
            path.unlink(missing_ok=True)

    def test_not_elf(self):
        from core.abi_scanner import _is_elf_binary
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"#!/bin/sh")
            path = Path(f.name)
        try:
            self.assertFalse(_is_elf_binary(path))
        finally:
            path.unlink(missing_ok=True)

    def test_missing(self):
        from core.abi_scanner import _is_elf_binary
        self.assertFalse(_is_elf_binary(Path("/nonexistent/x")))


class TestFlatpakEstimateSize(unittest.TestCase):

    def test_empty_dir_min_1(self):
        from core.flatpak_converter import _estimate_size_mb
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(_estimate_size_mb(Path(td)), 1)  # min 1 MB

    def test_sized_dir(self):
        from core.flatpak_converter import _estimate_size_mb
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "big.bin").write_bytes(b"\x00" * (3 * 1024 * 1024))
            self.assertEqual(_estimate_size_mb(Path(td)), 3)

    def test_nested_files(self):
        from core.flatpak_converter import _estimate_size_mb
        with tempfile.TemporaryDirectory() as td:
            sub = Path(td) / "a" / "b"
            sub.mkdir(parents=True)
            (sub / "f.bin").write_bytes(b"\x00" * (2 * 1024 * 1024))
            self.assertEqual(_estimate_size_mb(Path(td)), 2)


if __name__ == "__main__":
    unittest.main()
