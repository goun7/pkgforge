"""Tests for pure-logic modules: streaming, quality_score, dep_graph,
structured_log, completion, reproducible_build, from_source, config,
abi_scanner, snapshot_cleanup, delta_updater, rollback_verify."""

import json
import logging
import tempfile
import unittest
from pathlib import Path

from config import extract_package_name

# ELF magic: 0x7f E L F (built via bytes() to avoid source escapes)
ELF_MAGIC = bytes([0x7f, 0x45, 0x4c, 0x46])


class TestStreaming(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pkgforge_test_")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_stream_hash_sha256(self):
        from core.streaming import stream_hash
        f = self.dir / "data.bin"
        f.write_bytes(b"hello world")
        import hashlib
        expected = hashlib.sha256(b"hello world").hexdigest()
        self.assertEqual(stream_hash(f), expected)

    def test_stream_hash_md5(self):
        from core.streaming import stream_hash
        f = self.dir / "data.bin"
        f.write_bytes(b"abc")
        import hashlib
        self.assertEqual(stream_hash(f, "md5"), hashlib.md5(b"abc").hexdigest())

    def test_stream_copy(self):
        from core.streaming import stream_copy
        src = self.dir / "src.bin"
        dst = self.dir / "dst.bin"
        payload = b"x" * 200000
        src.write_bytes(payload)
        copied = stream_copy(src, dst, chunk_size=1024)
        self.assertEqual(copied, len(payload))
        self.assertEqual(dst.read_bytes(), payload)

    def test_stream_copy_progress(self):
        from core.streaming import stream_copy
        src = self.dir / "src.bin"
        dst = self.dir / "dst.bin"
        src.write_bytes(b"y" * 3000)
        calls = []
        stream_copy(src, dst, chunk_size=1000, progress_callback=lambda c, t: calls.append((c, t)))
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1], (3000, 3000))

    def test_chunked_read(self):
        from core.streaming import chunked_read
        f = self.dir / "data.bin"
        f.write_bytes(b"z" * 2500)
        chunks = list(chunked_read(f, chunk_size=1000))
        self.assertEqual(len(chunks), 3)
        self.assertEqual(b"".join(chunks), b"z" * 2500)

    def test_count_lines(self):
        from core.streaming import count_lines
        f = self.dir / "lines.txt"
        f.write_text("a\nb\nc\n")
        self.assertEqual(count_lines(f), 3)

    def test_get_file_size_human(self):
        from core.streaming import get_file_size_human
        f = self.dir / "small.bin"
        f.write_bytes(b"a" * 100)
        self.assertIn("B", get_file_size_human(f))
        big = self.dir / "big.bin"
        big.write_bytes(b"b" * (2 * 1024 * 1024))
        self.assertIn("MB", get_file_size_human(big))


class TestQualityReport(unittest.TestCase):

    def test_passed_threshold(self):
        from core.quality_score import QualityReport
        r = QualityReport(total_score=60, max_score=100)
        self.assertTrue(r.passed)
        r2 = QualityReport(total_score=59, max_score=100)
        self.assertFalse(r2.passed)

    def test_summary_contains_grade(self):
        from core.quality_score import QualityCheck, QualityReport
        r = QualityReport(package_name="demo", total_score=95, max_score=100, grade="A")
        r.checks.append(QualityCheck(name="X", category="security", passed=True, score=10, max_score=10, detail="ok"))
        s = r.summary()
        self.assertIn("demo", s)
        self.assertIn("A", s)
        self.assertIn("SECURITY", s)

    def test_summary_low_score(self):
        from core.quality_score import QualityReport
        r = QualityReport(package_name="bad", total_score=10, max_score=100, grade="F")
        self.assertIn("Kötü", r.summary())


class TestDepGraph(unittest.TestCase):

    def test_add_edge(self):
        from core.dep_graph import DepGraph
        g = DepGraph(root="app")
        g.add_edge("app", "libfoo")
        g.add_edge("app", "libbar")
        self.assertIn("libfoo", g.nodes["app"].deps)
        self.assertIn("app", g.nodes["libfoo"].needed_by)

    def test_add_edge_idempotent(self):
        from core.dep_graph import DepGraph
        g = DepGraph(root="app")
        g.add_edge("app", "libfoo")
        g.add_edge("app", "libfoo")
        self.assertEqual(g.nodes["app"].deps.count("libfoo"), 1)

    def test_to_mermaid(self):
        from core.dep_graph import DepGraph
        g = DepGraph(root="app")
        g.add_edge("app", "libfoo")
        m = g.to_mermaid()
        self.assertIn("graph TD", m)
        self.assertIn("app --> libfoo", m)

    def test_to_ascii(self):
        from core.dep_graph import DepGraph
        g = DepGraph(root="app")
        g.add_edge("app", "libfoo")
        a = g.to_ascii()
        self.assertIn("app", a)
        self.assertIn("libfoo", a)

    def test_stats(self):
        from core.dep_graph import DepGraph
        g = DepGraph(root="app")
        g.add_edge("app", "libfoo")
        g.nodes["app"].is_installed = True
        s = g.stats()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["installed"], 1)
        self.assertEqual(s["missing"], 1)


class TestStructuredLog(unittest.TestCase):

    def test_json_formatter(self):
        from core.structured_log import JSONFormatter
        fmt = JSONFormatter()
        record = logging.LogRecord("test", logging.INFO, "mod.py", 1, "hello", None, None)
        out = fmt.format(record)
        data = json.loads(out)
        self.assertEqual(data["message"], "hello")
        self.assertEqual(data["level"], "INFO")

    def test_json_formatter_exception(self):
        from core.structured_log import JSONFormatter
        fmt = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            record = logging.LogRecord("test", logging.ERROR, "mod.py", 1, "failed", None, sys.exc_info())
        out = fmt.format(record)
        data = json.loads(out)
        self.assertIn("exception", data)
        self.assertEqual(data["exception"]["type"], "ValueError")

    def test_human_formatter(self):
        from core.structured_log import HumanFormatter
        fmt = HumanFormatter(use_colors=False)
        record = logging.LogRecord("test", logging.WARNING, "mod.py", 1, "warn msg", None, None)
        out = fmt.format(record)
        self.assertIn("warn msg", out)
        self.assertIn("WARNING", out)


class TestCompletion(unittest.TestCase):

    def test_bash_completion(self):
        from core.completion import generate_completion
        s = generate_completion("bash")
        self.assertIn("_pkgforge", s)
        self.assertIn("complete -F", s)
        self.assertIn("convert", s)

    def test_zsh_completion(self):
        from core.completion import generate_completion
        s = generate_completion("zsh")
        self.assertIn("#compdef pkgforge", s)

    def test_fish_completion(self):
        from core.completion import generate_completion
        s = generate_completion("fish")
        self.assertIn("complete -c pkgforge", s)

    def test_invalid_shell(self):
        from core.completion import generate_completion
        with self.assertRaises(ValueError):
            generate_completion("powershell")


class TestReproducibleBuild(unittest.TestCase):

    def test_verify_missing_file(self):
        from config import ToolPaths
        from core.reproducible_build import verify_reproducible
        res = verify_reproducible(Path("/nonexistent.pkg.tar.zst"), ToolPaths())
        self.assertFalse(res.verified)
        self.assertIn("bulunamadı", res.detail)

    def test_verify_no_makepkg(self):
        from config import ToolPaths
        from core.reproducible_build import verify_reproducible
        with tempfile.NamedTemporaryFile(suffix=".pkg.tar.zst") as f:
            res = verify_reproducible(Path(f.name), ToolPaths())
            self.assertFalse(res.verified)
            self.assertIn("makepkg", res.detail)


class TestFromSourceVersionExtraction(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pkgforge_test_")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_extract_version_cargo(self):
        from core.from_source import _extract_version_from_cargo
        (self.dir / "Cargo.toml").write_text('[package]\nname = "x"\nversion = "1.2.3"\n')
        self.assertEqual(_extract_version_from_cargo(self.dir), "1.2.3")

    def test_extract_version_cmake(self):
        from core.from_source import _extract_version_from_cmake
        (self.dir / "CMakeLists.txt").write_text("project(myapp VERSION 2.0.1)")
        self.assertEqual(_extract_version_from_cmake(self.dir), "2.0.1")

    def test_extract_version_meson(self):
        from core.from_source import _extract_version_from_meson
        (self.dir / "meson.build").write_text("project('app', 'c', version: '3.1.0')")
        self.assertEqual(_extract_version_from_meson(self.dir), "3.1.0")

    def test_extract_version_pyproject(self):
        from core.from_source import _extract_version_from_pyproject
        (self.dir / "pyproject.toml").write_text('[project]\nversion = "0.9.0"\n')
        self.assertEqual(_extract_version_from_pyproject(self.dir), "0.9.0")

    def test_extract_version_file(self):
        from core.from_source import _extract_version_from_file
        (self.dir / "VERSION").write_text("4.5.6\n")
        self.assertEqual(_extract_version_from_file(self.dir), "4.5.6")

    def test_extract_version_missing(self):
        from core.from_source import _extract_version_from_cargo
        self.assertIsNone(_extract_version_from_cargo(self.dir))

    def test_detect_license_mit(self):
        from core.from_source import _detect_license
        (self.dir / "LICENSE").write_text("MIT License\nPermission is hereby granted, free of charge")
        self.assertEqual(_detect_license(self.dir), "MIT")


class TestAbiScanner(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pkgforge_test_")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_is_elf_binary(self):
        from core.abi_scanner import _is_elf_binary
        elf = self.dir / "prog"
        elf.write_bytes(ELF_MAGIC + bytes(60))
        self.assertTrue(_is_elf_binary(elf))
        txt = self.dir / "readme.txt"
        txt.write_text("not an elf")
        self.assertFalse(_is_elf_binary(txt))

    def test_is_elf_binary_missing(self):
        from core.abi_scanner import _is_elf_binary
        self.assertFalse(_is_elf_binary(self.dir / "nope"))

    def test_report_passed(self):
        from core.abi_scanner import ABIScanReport
        r = ABIScanReport(binary_count=3)
        self.assertTrue(r.passed)
        self.assertEqual(r.error_count, 0)

    def test_report_failed_with_mismatch(self):
        from core.abi_scanner import ABIScanReport, SymbolMismatch
        r = ABIScanReport(binary_count=1)
        r.mismatches.append(SymbolMismatch(
            binary="app", symbol="memcpy", required_version="GLIBC_2.99",
            available_version="GLIBC_2.38", library="libc.so.6",
        ))
        self.assertFalse(r.passed)
        self.assertEqual(r.error_count, 1)

    def test_report_summary(self):
        from core.abi_scanner import ABIScanReport
        r = ABIScanReport(binary_count=2, checked_symbols=10)
        s = r.summary()
        self.assertIn("2", s)
        self.assertIn("10", s)


class TestSnapshotCleanup(unittest.TestCase):

    def test_generate_cleanup_script(self):
        from core.snapshot_cleanup import _generate_cleanup_script
        s = _generate_cleanup_script(7)
        self.assertIn("#!/bin/bash", s)
        self.assertIn("MAX_AGE_DAYS=7", s)
        self.assertIn("btrfs", s)
        self.assertIn("zfs", s)

    def test_generate_service_unit(self):
        from core.snapshot_cleanup import _generate_service_unit
        s = _generate_service_unit()
        self.assertIn("[Unit]", s)
        self.assertIn("[Service]", s)
        self.assertIn("Type=oneshot", s)

    def test_generate_timer_unit(self):
        from core.snapshot_cleanup import _generate_timer_unit
        s = _generate_timer_unit(14)
        self.assertIn("[Timer]", s)
        self.assertIn("14", s)
        self.assertIn("timers.target", s)


class TestDeltaUpdater(unittest.TestCase):

    def test_is_xdelta3_available_returns_bool(self):
        from core.delta_updater import is_xdelta3_available
        self.assertIsInstance(is_xdelta3_available(), bool)

    def test_create_delta_missing_files(self):
        from unittest.mock import patch

        from core.delta_updater import create_delta
        with patch("core.delta_updater.is_xdelta3_available", return_value=True):
            ok = create_delta(Path("/no/old"), Path("/no/new"), Path("/no/delta"))
            self.assertFalse(ok)


class TestRollbackVerify(unittest.TestCase):

    def test_hash_file_tree_returns_hex(self):
        from core.rollback_verify import _hash_file_tree
        h = _hash_file_tree(Path("/etc"), max_files=5)
        self.assertEqual(len(h), 64)  # sha256 hex

    def test_result_defaults(self):
        from core.rollback_verify import RollbackVerifyResult
        r = RollbackVerifyResult()
        self.assertFalse(r.verified)
        self.assertEqual(r.backend, "none")


class TestExtractPackageName(unittest.TestCase):

    def test_deb_name(self):
        self.assertEqual(extract_package_name("libssl1.1_1.1.0-1_amd64.deb"), "libssl1.1")

    def test_deb_simple(self):
        self.assertEqual(extract_package_name("hello_1.0.0-1_amd64.deb"), "hello")

    def test_rpm_name(self):
        self.assertEqual(extract_package_name("openssl-1.1.1k-4-x86_64.rpm"), "openssl")

    def test_rpm_epoch(self):
        self.assertEqual(extract_package_name("1:vim-9.0-1.x86_64.rpm"), "vim")

    def test_arch_pkg(self):
        self.assertEqual(extract_package_name("hello-1.0.0-1-x86_64.pkg.tar.zst"), "hello")

    def test_url_basename(self):
        self.assertEqual(extract_package_name("https://example.com/dl/foo_2.0-1_amd64.deb"), "foo")


if __name__ == "__main__":
    unittest.main()
