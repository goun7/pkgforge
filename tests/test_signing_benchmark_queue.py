"""Tests for signing, sigstore, benchmark, and queue dataclasses."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestPackageSigning(unittest.TestCase):

    def test_is_gpg_available_returns_bool(self):
        from core.package_signing import is_gpg_available
        self.assertIsInstance(is_gpg_available(), bool)

    def test_signature_info_defaults(self):
        from core.package_signing import SignatureInfo
        info = SignatureInfo()
        self.assertFalse(info.signed)
        self.assertFalse(info.valid)
        self.assertEqual(info.key_id, "")

    def test_sign_package_missing_file(self):
        from core.package_signing import sign_package
        with patch("core.package_signing.is_gpg_available", return_value=True):
            ok, msg = sign_package(Path("/nonexistent.pkg.tar.zst"))
            self.assertFalse(ok)
            self.assertIn("bulunamadı", msg)

    def test_sign_package_no_gpg(self):
        from core.package_signing import sign_package
        with patch("core.package_signing.is_gpg_available", return_value=False):
            ok, msg = sign_package(Path("/some.pkg.tar.zst"))
            self.assertFalse(ok)
            self.assertIn("gpg", msg)

    def test_verify_signature_no_sig_file(self):
        from core.package_signing import verify_signature
        with patch("core.package_signing.is_gpg_available", return_value=True):
            with tempfile.NamedTemporaryFile(suffix=".pkg.tar.zst") as f:
                info = verify_signature(Path(f.name))
                self.assertFalse(info.valid)
                self.assertIn("bulunamadı", info.detail)

    def test_verify_signature_parses_goodsig(self):
        from core.package_signing import verify_signature
        gpg_status = (
            "[GNUPG:] GOODSIG ABCD1234 Test Signer\n"
            "[GNUPG:] VALIDSIG DEADBEEF1234567890\n"
            "[GNUPG:] TRUST_FULLY\n"
        )
        mock_res = MagicMock(returncode=0, stdout=gpg_status, stderr="")
        with patch("core.package_signing.is_gpg_available", return_value=True), \
             patch("core.package_signing.safe_run", return_value=mock_res):
            with tempfile.TemporaryDirectory() as td:
                pkg = Path(td) / "test.pkg.tar.zst"
                pkg.write_bytes(b"data")
                sig = Path(td) / "test.pkg.tar.zst.sig"
                sig.write_bytes(b"sig")
                info = verify_signature(pkg)
                self.assertTrue(info.signed)
                self.assertTrue(info.valid)
                self.assertEqual(info.key_id, "ABCD1234")

    def test_list_keys_parses_colons(self):
        from core.package_signing import list_keys
        gpg_out = (
            "pub:u:4096:1:ABCD1234:1700000000::u:::scESC::::::23::0:\n"
            "uid:u::::1700000000::HASH::Test User <test@example.com>::::::::::0:\n"
        )
        mock_res = MagicMock(returncode=0, stdout=gpg_out, stderr="")
        with patch("core.package_signing.is_gpg_available", return_value=True), \
             patch("core.package_signing.safe_run", return_value=mock_res):
            keys = list_keys()
            self.assertEqual(len(keys), 1)
            self.assertEqual(keys[0]["key_id"], "ABCD1234")
            self.assertIn("Test User", keys[0]["uid"])


class TestSigstore(unittest.TestCase):

    def test_result_summary_success(self):
        from core.sigstore import SigstoreResult
        r = SigstoreResult(success=True, message="signed", log_index="12345")
        s = r.summary()
        self.assertIn("signed", s)
        self.assertIn("12345", s)

    def test_result_summary_failure(self):
        from core.sigstore import SigstoreResult
        r = SigstoreResult(success=False, message="failed")
        self.assertIn("failed", r.summary())

    def test_find_cosign(self):
        from core.sigstore import _find_cosign
        result = _find_cosign()
        self.assertTrue(result is None or isinstance(result, str))

    def test_sign_no_cosign(self):
        from core.sigstore import sign_with_sigstore
        with patch("core.sigstore._find_cosign", return_value=None):
            r = sign_with_sigstore(Path("/some/file"))
            self.assertFalse(r.success)
            self.assertIn("cosign", r.message)

    def test_sign_missing_file(self):
        from core.sigstore import sign_with_sigstore
        with patch("core.sigstore._find_cosign", return_value="/usr/bin/cosign"):
            r = sign_with_sigstore(Path("/nonexistent/file.deb"))
            self.assertFalse(r.success)
            self.assertIn("bulunamadı", r.message)

    def test_verify_no_cosign(self):
        from core.sigstore import verify_with_sigstore
        with patch("core.sigstore._find_cosign", return_value=None):
            r = verify_with_sigstore(Path("/some/file"))
            self.assertFalse(r.success)

    def test_get_sigstore_status_no_cosign(self):
        from core.sigstore import get_sigstore_status
        with patch("core.sigstore._find_cosign", return_value=None):
            status = get_sigstore_status()
            self.assertFalse(status["cosign_available"])


class TestBenchmark(unittest.TestCase):

    def test_benchmark_result_defaults(self):
        from core.benchmark import BenchmarkResult
        r = BenchmarkResult(name="test")
        self.assertEqual(r.name, "test")
        self.assertTrue(r.passed)

    def test_benchmark_report_passed(self):
        from core.benchmark import BenchmarkReport, BenchmarkResult
        rep = BenchmarkReport()
        rep.results.append(BenchmarkResult(name="a", passed=True))
        rep.results.append(BenchmarkResult(name="b", passed=True))
        self.assertTrue(rep.passed)
        rep.results.append(BenchmarkResult(name="c", passed=False))
        self.assertFalse(rep.passed)

    def test_benchmark_report_summary(self):
        from core.benchmark import BenchmarkReport, BenchmarkResult
        rep = BenchmarkReport(total_duration_ms=1500)
        rep.results.append(BenchmarkResult(name="convert", duration_ms=500, memory_peak_kb=2048))
        s = rep.summary()
        self.assertIn("convert", s)
        self.assertIn("Toplam", s)

    def test_get_memory_usage(self):
        from core.benchmark import _get_memory_usage
        mem = _get_memory_usage()
        self.assertIsInstance(mem, int)
        self.assertGreaterEqual(mem, 0)


class TestQueueItem(unittest.TestCase):

    def test_queue_item_status_values(self):
        from core.queue_manager import QueueItemStatus
        self.assertEqual(QueueItemStatus.PENDING.value, "pending")
        self.assertEqual(QueueItemStatus.DONE.value, "done")
        self.assertEqual(QueueItemStatus.ERROR.value, "error")

    def test_queue_item_name(self):
        from core.queue_manager import QueueItem
        item = QueueItem(file_path=Path("/tmp/hello_1.0-1_amd64.deb"))
        self.assertEqual(item.name, "hello_1.0-1_amd64.deb")

    def test_queue_item_pkg_type_deb(self):
        from core.queue_manager import QueueItem
        item = QueueItem(file_path=Path("/tmp/app.deb"))
        self.assertEqual(item.pkg_type, "deb")

    def test_queue_item_pkg_type_rpm(self):
        from core.queue_manager import QueueItem
        item = QueueItem(file_path=Path("/tmp/app.rpm"))
        self.assertEqual(item.pkg_type, "rpm")

    def test_queue_item_default_status(self):
        from core.queue_manager import QueueItem, QueueItemStatus
        item = QueueItem(file_path=Path("/tmp/x.deb"))
        self.assertEqual(item.status, QueueItemStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
