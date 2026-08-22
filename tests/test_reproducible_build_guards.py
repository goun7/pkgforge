"""Tests for reproducible_build guard paths.

Exercises the graceful-degradation branches: missing package file and
missing makepkg. Full rebuild verification requires a real makepkg run.
"""

import unittest
from pathlib import Path


class TestVerifyReproducibleGuards(unittest.TestCase):

    def test_missing_package(self):
        from config import discover_tools
        from core.reproducible_build import verify_reproducible
        result = verify_reproducible(
            Path("/nonexistent/x.pkg.tar.zst"), discover_tools()
        )
        self.assertFalse(result.verified)
        self.assertIn("bulunamad", result.detail)  # bulunamadı (not found)

    def test_missing_makepkg(self):
        import tempfile

        from config import ToolPaths
        from core.reproducible_build import verify_reproducible
        with tempfile.NamedTemporaryFile(suffix=".pkg.tar.zst", delete=False) as f:
            f.write(b"fake")
            path = Path(f.name)
        try:
            tools = ToolPaths(makepkg="")  # no makepkg
            result = verify_reproducible(path, tools)
            self.assertFalse(result.verified)
            self.assertIn("makepkg", result.detail)
        finally:
            path.unlink(missing_ok=True)


class TestVerifyResultDataclass(unittest.TestCase):

    def test_defaults(self):
        from core.reproducible_build import VerifyResult
        r = VerifyResult()
        self.assertFalse(r.verified)
        self.assertEqual(r.match_ratio, 0.0)
        self.assertEqual(r.diff_size, 0)


if __name__ == "__main__":
    unittest.main()
