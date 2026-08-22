"""Tests for streaming, retry, report_export, and sbom diff logic.

All hermetic: temp files and in-memory objects only.
"""

import tempfile
import unittest
from pathlib import Path


class TestStreamHash(unittest.TestCase):

    def test_sha256(self):
        import hashlib
        from core.streaming import stream_hash
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            path = Path(f.name)
        try:
            expected = hashlib.sha256(b"hello world").hexdigest()
            self.assertEqual(stream_hash(path), expected)
        finally:
            path.unlink(missing_ok=True)

    def test_md5(self):
        import hashlib
        from core.streaming import stream_hash
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"abc")
            path = Path(f.name)
        try:
            expected = hashlib.md5(b"abc").hexdigest()
            self.assertEqual(stream_hash(path, algorithm="md5"), expected)
        finally:
            path.unlink(missing_ok=True)

    def test_empty_file(self):
        import hashlib
        from core.streaming import stream_hash
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = Path(f.name)
        try:
            self.assertEqual(stream_hash(path), hashlib.sha256(b"").hexdigest())
        finally:
            path.unlink(missing_ok=True)


class TestStreamCopy(unittest.TestCase):

    def test_copy_roundtrip(self):
        from core.streaming import stream_copy
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.bin"
            dst = Path(td) / "dst.bin"
            data = b"x" * 10000
            src.write_bytes(data)
            n = stream_copy(src, dst, chunk_size=1024)
            self.assertEqual(n, 10000)
            self.assertEqual(dst.read_bytes(), data)

    def test_progress_callback(self):
        from core.streaming import stream_copy
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.bin"
            dst = Path(td) / "dst.bin"
            src.write_bytes(b"y" * 2048)
            calls = []
            stream_copy(src, dst, chunk_size=1024,
                        progress_callback=lambda c, t: calls.append((c, t)))
            self.assertEqual(calls[-1], (2048, 2048))


class TestChunkedRead(unittest.TestCase):

    def test_yields_chunks(self):
        from core.streaming import chunked_read
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"a" * 300)
            path = Path(f.name)
        try:
            chunks = list(chunked_read(path, chunk_size=100))
            self.assertEqual(len(chunks), 3)
            self.assertEqual(b"".join(chunks), b"a" * 300)
        finally:
            path.unlink(missing_ok=True)


class TestCountLines(unittest.TestCase):

    def test_count(self):
        from core.streaming import count_lines
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("a\nb\nc\n")
            path = Path(f.name)
        try:
            self.assertEqual(count_lines(path), 3)
        finally:
            path.unlink(missing_ok=True)

    def test_empty(self):
        from core.streaming import count_lines
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            path = Path(f.name)
        try:
            self.assertEqual(count_lines(path), 0)
        finally:
            path.unlink(missing_ok=True)


class TestGetFileSizeHuman(unittest.TestCase):

    def _size(self, n):
        from core.streaming import get_file_size_human
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"\0" * n)
            path = Path(f.name)
        try:
            return get_file_size_human(path)
        finally:
            path.unlink(missing_ok=True)

    def test_bytes(self):
        self.assertIn("B", self._size(100))

    def test_kb(self):
        self.assertIn("KB", self._size(2048))

    def test_mb(self):
        self.assertIn("MB", self._size(2 * 1024 * 1024))


class TestRetryConfig(unittest.TestCase):

    def test_delay_exponential(self):
        from core.retry import RetryConfig
        cfg = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=30.0, jitter=False)
        self.assertEqual(cfg.get_delay(0), 1.0)
        self.assertEqual(cfg.get_delay(1), 2.0)
        self.assertEqual(cfg.get_delay(2), 4.0)

    def test_delay_capped(self):
        from core.retry import RetryConfig
        cfg = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=5.0, jitter=False)
        self.assertEqual(cfg.get_delay(10), 5.0)

    def test_jitter_within_bounds(self):
        from core.retry import RetryConfig
        cfg = RetryConfig(base_delay=2.0, backoff_factor=1.0, max_delay=30.0, jitter=True)
        for _ in range(20):
            d = cfg.get_delay(0)
            self.assertGreaterEqual(d, 1.0)   # 50% of 2.0
            self.assertLessEqual(d, 2.0)      # 100% of 2.0


class TestRetryWithBackoff(unittest.TestCase):

    def test_success_first_try(self):
        from core.retry import RetryConfig, retry_with_backoff
        cfg = RetryConfig(base_delay=0.001, jitter=False)
        self.assertEqual(retry_with_backoff(lambda: 42, cfg), 42)

    def test_success_after_retries(self):
        from core.retry import RetryConfig, retry_with_backoff
        cfg = RetryConfig(max_retries=3, base_delay=0.001, jitter=False)
        attempts = {"n": 0}
        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise ConnectionError("transient")
            return "ok"
        self.assertEqual(retry_with_backoff(flaky, cfg), "ok")
        self.assertEqual(attempts["n"], 3)

    def test_exhausted_raises(self):
        from core.retry import RetryConfig, retry_with_backoff
        cfg = RetryConfig(max_retries=2, base_delay=0.001, jitter=False)
        def always_fail():
            raise TimeoutError("nope")
        with self.assertRaises(TimeoutError):
            retry_with_backoff(always_fail, cfg)

    def test_non_retryable_raises_immediately(self):
        from core.retry import RetryConfig, retry_with_backoff
        cfg = RetryConfig(max_retries=5, base_delay=0.001, jitter=False)
        attempts = {"n": 0}
        def bad():
            attempts["n"] += 1
            raise ValueError("not retryable")
        with self.assertRaises(ValueError):
            retry_with_backoff(bad, cfg)
        self.assertEqual(attempts["n"], 1)  # no retries for non-retryable


class TestSbomDiff(unittest.TestCase):

    def _doc(self, name, version, files, deps):
        from core.sbom import SBOMDocument, SBOMEntry
        entries = [SBOMEntry(path=p, sha256=h) for p, h in files]
        return SBOMDocument(
            package_name=name, package_version=version,
            files=entries, dependencies=deps,
            total_files=len(entries),
        )

    def test_added_removed_files(self):
        from core.sbom import diff_sboms
        old = self._doc("p", "1", [("a", "h1"), ("b", "h2")], [])
        new = self._doc("p", "2", [("b", "h2"), ("c", "h3")], [])
        d = diff_sboms(old, new)
        self.assertEqual(d.added_files, ["c"])
        self.assertEqual(d.removed_files, ["a"])

    def test_changed_files(self):
        from core.sbom import diff_sboms
        old = self._doc("p", "1", [("a", "hash_old_xxxxxxxxxxxxxxxx")], [])
        new = self._doc("p", "2", [("a", "hash_new_xxxxxxxxxxxxxxxx")], [])
        d = diff_sboms(old, new)
        self.assertEqual(len(d.changed_files), 1)
        self.assertEqual(d.changed_files[0]["path"], "a")

    def test_unchanged_not_flagged(self):
        from core.sbom import diff_sboms
        old = self._doc("p", "1", [("a", "same")], [])
        new = self._doc("p", "2", [("a", "same")], [])
        d = diff_sboms(old, new)
        self.assertEqual(d.changed_files, [])

    def test_dep_diff(self):
        from core.sbom import diff_sboms
        old = self._doc("p", "1", [], ["libc.so.6", "libm.so.6"])
        new = self._doc("p", "2", [], ["libc.so.6", "libz.so.1"])
        d = diff_sboms(old, new)
        self.assertEqual(d.added_deps, ["libz.so.1"])
        self.assertEqual(d.removed_deps, ["libm.so.6"])


class TestSbomDetectFileType(unittest.TestCase):

    def _detect(self, data):
        from core.sbom import _detect_file_type
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            path = Path(f.name)
        try:
            return _detect_file_type(path)
        finally:
            path.unlink(missing_ok=True)

    def test_elf(self):
        self.assertEqual(self._detect(bytes([0x7f, 0x45, 0x4c, 0x46]) + b"\0"), "elf")

    def test_shebang_text(self):
        self.assertEqual(self._detect(b"#!/bin/sh\n"), "text")

    def test_binary(self):
        self.assertEqual(self._detect(bytes([0x00, 0x01, 0x02, 0x03])), "binary")

    def test_missing(self):
        from core.sbom import _detect_file_type
        self.assertEqual(_detect_file_type(Path("/nonexistent/x")), "")


class TestSbomDocument(unittest.TestCase):

    def test_to_dict_roundtrip(self):
        from core.sbom import SBOMDocument, SBOMEntry
        doc = SBOMDocument(
            package_name="hello", package_version="1.0",
            files=[SBOMEntry(path="usr/bin/hello", file_type="elf", sha256="ab")],
            dependencies=["libc.so.6"],
        )
        d = doc.to_dict()
        self.assertEqual(d["package_name"], "hello")
        self.assertEqual(d["files"][0]["path"], "usr/bin/hello")
        self.assertEqual(d["dependencies"], ["libc.so.6"])

    def test_summary_contains_name(self):
        from core.sbom import SBOMDocument
        doc = SBOMDocument(package_name="hello", package_version="1.0")
        self.assertIn("hello", doc.summary())


if __name__ == "__main__":
    unittest.main()
