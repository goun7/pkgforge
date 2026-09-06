"""Tests for downloader redirect scheme guard and benchmark test-deb generator.

The scheme guard is tested with real urllib Request objects (no network).
The benchmark generator builds a REAL .deb with tar+ar, which is then
round-tripped through analyze_package to prove it is a valid package.
"""

import tempfile
import unittest
import urllib.request
from pathlib import Path


class TestSchemeGuardRedirectHandler(unittest.TestCase):

    def _req(self):
        return urllib.request.Request("https://example.com/file.deb")

    def test_https_redirect_allowed(self):
        from core.downloader import _SchemeGuardRedirectHandler
        h = _SchemeGuardRedirectHandler(require_https=True,
                                        allow_private_hosts=True)
        new = h.redirect_request(
            self._req(), None, 302, "Found", {},
            "https://cdn.example.com/file.deb",
        )
        self.assertEqual(new.full_url, "https://cdn.example.com/file.deb")

    def test_http_downgrade_blocked(self):
        from core.downloader import _SchemeGuardRedirectHandler
        h = _SchemeGuardRedirectHandler(require_https=True)
        with self.assertRaises(ValueError):
            h.redirect_request(
                self._req(), None, 302, "Found", {},
                "http://evil.example.com/file.deb",
            )

    def test_non_http_scheme_blocked(self):
        from core.downloader import _SchemeGuardRedirectHandler
        h = _SchemeGuardRedirectHandler(require_https=False)
        with self.assertRaises(ValueError):
            h.redirect_request(
                self._req(), None, 302, "Found", {},
                "ftp://evil.example.com/file.deb",
            )

    def test_http_allowed_when_not_requiring_https(self):
        from core.downloader import _SchemeGuardRedirectHandler
        h = _SchemeGuardRedirectHandler(require_https=False,
                                        allow_private_hosts=True)
        new = h.redirect_request(
            self._req(), None, 302, "Found", {},
            "http://cdn.example.com/file.deb",
        )
        self.assertEqual(new.full_url, "http://cdn.example.com/file.deb")


class TestBenchmarkHelpers(unittest.TestCase):

    def test_get_memory_usage(self):
        from core.benchmark import _get_memory_usage
        # On Linux /proc is available; must return a positive KB count
        mem = _get_memory_usage()
        self.assertIsInstance(mem, int)
        self.assertGreater(mem, 0)

    def test_create_test_deb_is_valid(self):
        from core.benchmark import _create_test_deb
        with tempfile.TemporaryDirectory() as td:
            deb = Path(td) / "benchmark-test.deb"
            self.assertTrue(_create_test_deb(deb))
            self.assertTrue(deb.is_file())
            self.assertGreater(deb.stat().st_size, 0)
            # Must be a real ar archive with the three deb members
            import subprocess
            res = subprocess.run(["ar", "t", str(deb)],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0)
            members = res.stdout.split()
            self.assertIn("debian-binary", members)
            self.assertIn("control.tar.gz", members)
            self.assertIn("data.tar.gz", members)

    def test_create_test_deb_roundtrip_analyze(self):
        from config import discover_tools
        from core.benchmark import _create_test_deb
        from core.package_analyzer import analyze_package
        with tempfile.TemporaryDirectory() as td:
            deb = Path(td) / "benchmark-test.deb"
            self.assertTrue(_create_test_deb(deb))
            meta = analyze_package(deb, discover_tools())
            self.assertEqual(meta.name, "benchmark-test")
            self.assertEqual(meta.version, "1.0.0")
            self.assertEqual(meta.arch, "amd64")


if __name__ == "__main__":
    unittest.main()
