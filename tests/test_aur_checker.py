"""Unit tests for core/aur_checker.py search_aur (Faz 2 / B1)."""

import json
import unittest
from unittest.mock import MagicMock, patch

from core.aur_checker import _version_compare, check_aur, search_aur


class TestAurChecker(unittest.TestCase):

    def test_version_compare(self):
        self.assertEqual(_version_compare("1.0.0", "1.0.0"), 0)
        self.assertTrue(_version_compare("2.0.0", "1.0.0") > 0)
        self.assertTrue(_version_compare("1.0.0", "2.0.0") < 0)
        self.assertTrue(_version_compare("1.2.3-2", "1.2.3-1") >= 0)

    def test_check_aur_empty(self):
        res = check_aur("")
        self.assertEqual(res.status, "error")
        self.assertIn("Boş", res.detail)


class TestSearchAur(unittest.TestCase):

    def test_search_empty_query(self):
        self.assertEqual(search_aur(""), [])

    def test_search_offline(self):
        self.assertEqual(search_aur("firefox", offline=True), [])

    @patch("core.aur_checker.urllib.request.urlopen")
    def test_search_parses_results(self, mock_urlopen):
        payload = {
            "resultcount": 2,
            "results": [
                {
                    "Name": "firefox-bin",
                    "Version": "128.0-1",
                    "Description": "Standalone web browser (binary)",
                    "NumVotes": 1200,
                    "OutOfDate": None,
                    "URLPath": "/cgit/aur.git/snapshot/firefox-bin.tar.gz",
                },
                {
                    "Name": "firefox-i18n-tr",
                    "Version": "128.0-1",
                    "Description": "Turkish language pack",
                    "NumVotes": 45,
                    "OutOfDate": 1700000000,
                    "URLPath": "/cgit/aur.git/snapshot/firefox-i18n-tr.tar.gz",
                },
            ],
        }
        resp = MagicMock()
        resp.read.return_value = json.dumps(payload).encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        results = search_aur("firefox", limit=10)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "firefox-bin")
        self.assertEqual(results[0]["version"], "128.0-1")
        self.assertEqual(results[0]["num_votes"], 1200)
        self.assertFalse(results[0]["out_of_date"])
        self.assertTrue(results[1]["out_of_date"])

    @patch("core.aur_checker.urllib.request.urlopen")
    def test_search_limit_applied(self, mock_urlopen):
        payload = {
            "resultcount": 3,
            "results": [
                {"Name": f"pkg{i}", "Version": "1.0", "Description": "", "NumVotes": 0,
                 "OutOfDate": None, "URLPath": ""}
                for i in range(3)
            ],
        }
        resp = MagicMock()
        resp.read.return_value = json.dumps(payload).encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        results = search_aur("pkg", limit=2)
        self.assertEqual(len(results), 2)

    @patch("core.aur_checker.urllib.request.urlopen")
    def test_search_network_error_returns_empty(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("no network")
        self.assertEqual(search_aur("firefox"), [])


if __name__ == "__main__":
    unittest.main()
