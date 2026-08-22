"""Integration tests: run_compatibility_checks on a real package + check_aur offline.

run_compatibility_checks exercises namcap, dependency resolution, file
conflicts, and shared-library checks against the tracked lictest fixture.
"""

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LICTEST_PKG = PROJECT_ROOT / "utest" / "lictest" / "lictest-1.0.0-1-any.pkg.tar.zst"


@unittest.skipUnless(LICTEST_PKG.is_file(), "lictest fixture missing")
class TestRunCompatibilityChecks(unittest.TestCase):

    def test_real_package(self):
        from config import discover_tools
        from core.compatibility_checker import (
            CompatibilityReport, run_compatibility_checks,
        )
        tools = discover_tools()
        report = run_compatibility_checks(
            pkg_path=LICTEST_PKG,
            file_list=["usr/bin/lictest"],
            depends=[],
            tools=tools,
        )
        self.assertIsInstance(report, CompatibilityReport)
        # Must have run at least namcap + file-conflict checks
        self.assertGreaterEqual(len(report.checks), 2)
        # overall/grade must be computable without error
        self.assertIn(report.grade, ("A", "B", "C", "D", "F"))

    def test_empty_file_list(self):
        from config import discover_tools
        from core.compatibility_checker import run_compatibility_checks
        tools = discover_tools()
        report = run_compatibility_checks(
            pkg_path=LICTEST_PKG, file_list=[], depends=[], tools=tools,
        )
        self.assertGreaterEqual(len(report.checks), 1)


class TestCheckAurOffline(unittest.TestCase):

    def test_empty_name(self):
        from core.aur_checker import check_aur
        res = check_aur("")
        self.assertEqual(res.status, "error")

    def test_offline(self):
        from core.aur_checker import check_aur
        res = check_aur("hello", offline=True)
        self.assertEqual(res.status, "error")
        self.assertIn("evrimd", res.detail)  # Çevrimdışı (offline) message


if __name__ == "__main__":
    unittest.main()
