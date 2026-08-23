"""Unit tests for core/cve_scanner.py (Faz 2 / B4)."""

import json
import unittest
from unittest.mock import MagicMock, patch

from core.cve_scanner import scan_dependencies


class TestCveScanner(unittest.TestCase):

    def test_empty_deps(self):
        result = scan_dependencies([])
        self.assertEqual(result["deps_scanned"], 0)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["vulns"], [])

    def test_offline_mode(self):
        result = scan_dependencies(["glibc", "openssl"], offline=True)
        self.assertEqual(result["count"], 0)
        self.assertTrue(result["offline"])

    @patch("core.cve_scanner.urllib.request.urlopen")
    def test_scan_parses_osv_response(self, mock_urlopen):
        osv_payload = {
            "vulns": [
                {
                    "id": "CVE-2023-1234",
                    "summary": "Buffer overflow in openssl",
                    "database_specific": {"severity": "HIGH"},
                },
            ],
        }
        resp = MagicMock()
        resp.read.return_value = json.dumps(osv_payload).encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = scan_dependencies(["openssl"])
        self.assertEqual(result["deps_scanned"], 1)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["vulns"][0]["id"], "CVE-2023-1234")
        self.assertEqual(result["vulns"][0]["affected_dep"], "openssl")

    @patch("core.cve_scanner.urllib.request.urlopen")
    def test_scan_network_error_graceful(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("no network")
        result = scan_dependencies(["openssl"])
        self.assertEqual(result["count"], 0)
        self.assertTrue(result["offline"])

    @patch("core.cve_scanner.urllib.request.urlopen")
    def test_scan_dedupes_vulns(self, mock_urlopen):
        osv_payload = {
            "vulns": [
                {"id": "CVE-2023-1", "summary": "a", "database_specific": {"severity": "LOW"}},
                {"id": "CVE-2023-1", "summary": "a", "database_specific": {"severity": "LOW"}},
            ],
        }
        resp = MagicMock()
        resp.read.return_value = json.dumps(osv_payload).encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = scan_dependencies(["openssl"])
        self.assertEqual(result["count"], 1)


if __name__ == "__main__":
    unittest.main()
