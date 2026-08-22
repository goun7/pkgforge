"""Tests for oci_builder guard paths (no container runtime in CI).

buildah/podman are not installed in the sandbox, so these exercise the
graceful-degradation branches: runtime detection and missing-file/runtime errors.
"""

import shutil
import tempfile
import unittest
from pathlib import Path


class TestOciBuilderGuards(unittest.TestCase):

    def test_runtime_available_returns_bool(self):
        from core.oci_builder import is_container_runtime_available
        result = is_container_runtime_available()
        self.assertIsInstance(result, bool)
        # Must agree with actual tool presence
        expected = bool(shutil.which("buildah") or shutil.which("podman"))
        self.assertEqual(result, expected)

    def test_missing_package_file(self):
        from config import discover_tools
        from core.oci_builder import build_oci_image
        ok, msg, out = build_oci_image(
            Path("/nonexistent/x.pkg.tar.zst"), discover_tools()
        )
        self.assertFalse(ok)
        self.assertIsNone(out)
        self.assertIn("bulunamad", msg)  # bulunamadı (not found)

    @unittest.skipIf(
        shutil.which("buildah") or shutil.which("podman"),
        "container runtime present — guard path not reachable",
    )
    def test_no_runtime_graceful(self):
        from config import discover_tools
        from core.oci_builder import build_oci_image
        with tempfile.NamedTemporaryFile(suffix=".pkg.tar.zst", delete=False) as f:
            f.write(b"fake")
            path = Path(f.name)
        try:
            ok, msg, out = build_oci_image(path, discover_tools())
            self.assertFalse(ok)
            self.assertIsNone(out)
            self.assertIn("buildah", msg)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
