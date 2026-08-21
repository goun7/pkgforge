"""Unit tests for snapshot_manager, malware_scanner, delta_updater, oci_builder."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.delta_updater import (
    apply_delta,
    create_delta,
    find_local_previous,
    is_xdelta3_available,
)
from core.malware_scanner import ScanResult, scan_file
from core.oci_builder import build_oci_image
from core.snapshot_manager import (
    detect_backend,
    take_snapshot,
)

# ── Malware Scanner Tests ──────────────────────────────────────

class TestMalwareScanner(unittest.TestCase):

    def test_scan_result_defaults(self):
        r = ScanResult()
        self.assertTrue(r.clean)
        self.assertFalse(r.infected)
        self.assertEqual(r.infected_files, [])

    def test_scan_file_nonexistent(self):
        result = scan_file(Path("/nonexistent/file.deb"), MagicMock())
        self.assertFalse(result.clean)
        self.assertIn("bulunamadı", result.detail)

    @patch("core.malware_scanner.safe_run")
    @patch("core.malware_scanner.shutil.which", return_value="/usr/bin/clamscan")
    def test_scan_file_clean(self, _mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        with tempfile.NamedTemporaryFile(suffix=".deb") as f:
            result = scan_file(Path(f.name), MagicMock())
            self.assertTrue(result.clean)

    @patch("core.malware_scanner.safe_run")
    @patch("core.malware_scanner.shutil.which", return_value="/usr/bin/clamscan")
    def test_scan_file_infected(self, _mock_which, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="/tmp/evil.deb: Win.Test.EICAR FOUND\n",
            stderr="",
        )
        with tempfile.NamedTemporaryFile(suffix=".deb") as f:
            result = scan_file(Path(f.name), MagicMock())
            self.assertFalse(result.clean)
            self.assertTrue(result.infected)
            self.assertTrue(len(result.infected_files) > 0)

    @patch("core.malware_scanner.safe_run")
    @patch("core.malware_scanner.shutil.which", return_value=None)
    def test_scan_file_no_clamscan(self, _mock_which, _mock_run):
        """File exists but clamscan is missing — should skip gracefully."""
        with tempfile.NamedTemporaryFile(suffix=".deb") as f:
            result = scan_file(Path(f.name), MagicMock())
            self.assertTrue(result.clean)
            self.assertIn("clamscan bulunamadı", result.detail)


# ── Delta Updater Tests ────────────────────────────────────────

class TestDeltaUpdater(unittest.TestCase):

    def test_create_and_apply_delta(self):
        if not is_xdelta3_available():
            self.skipTest("xdelta3 not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            old = Path(tmpdir) / "old.bin"
            new = Path(tmpdir) / "new.bin"
            delta = Path(tmpdir) / "delta.xdelta"
            output = Path(tmpdir) / "output.bin"

            old.write_bytes(b"AAAA" * 100)
            new.write_bytes(b"AAAA" * 99 + b"BBBB")

            self.assertTrue(create_delta(old, new, delta))
            self.assertTrue(delta.exists())
            self.assertLess(delta.stat().st_size, new.stat().st_size)

            self.assertTrue(apply_delta(old, delta, output))
            self.assertEqual(output.read_bytes(), new.read_bytes())

    def test_create_delta_nonexistent(self):
        result = create_delta(Path("/no/old"), Path("/no/new"), Path("/no/delta"))
        self.assertFalse(result)

    def test_find_local_previous_no_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_local_previous("nonexistent-pkg", Path(tmpdir))
            self.assertIsNone(result)

    def test_find_local_previous_finds_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir) / "someapp-1.0-1-x86_64.pkg.tar.zst"
            pkg.write_bytes(b"fake")
            result = find_local_previous("someapp", Path(tmpdir))
            self.assertIsNotNone(result)
            self.assertEqual(result.name, pkg.name)


# ── OCI Builder Tests ──────────────────────────────────────────

class TestOciBuilder(unittest.TestCase):

    def test_build_nonexistent_file(self):
        ok, msg, _path = build_oci_image(Path("/nonexistent.deb"), MagicMock())
        self.assertFalse(ok)
        self.assertIn("bulunamadı", msg)

    @patch("core.oci_builder.shutil.which", return_value=None)
    @patch("core.oci_builder.shutil.which")  # Both buildah and podman
    def test_build_no_runtime(self, _mock_buildah, _mock_podman):
        """Both buildah and podman missing — should fail."""
        # Create a temp file so existence check passes
        with tempfile.NamedTemporaryFile(suffix=".deb") as f:
            ok, msg, _path = build_oci_image(Path(f.name), MagicMock())
            self.assertFalse(ok)
            self.assertIn("buildah", msg.lower())


# ── Snapshot Manager Tests ─────────────────────────────────────

class TestSnapshotManager(unittest.TestCase):

    def test_detect_backend_returns_string(self):
        result = detect_backend()
        self.assertIn(result, ("btrfs", "zfs", "none"))

    def test_take_snapshot_no_backend(self):
        with patch("core.snapshot_manager.detect_backend", return_value="none"):
            result = take_snapshot("test")
            self.assertFalse(result.success)
            self.assertEqual(result.backend, "none")


if __name__ == "__main__":
    unittest.main()
