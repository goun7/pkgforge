"""Unit tests for core/compatibility_checker.py."""

import unittest
from core.compatibility_checker import (
    CheckSeverity,
    CheckResult,
    CompatibilityReport,
    _check_file_conflicts,
    _run_namcap,
)
from config import ToolPaths


class TestCompatibilityChecker(unittest.TestCase):

    def test_compatibility_report_overall(self):
        report = CompatibilityReport()
        report.checks.append(CheckResult("Test1", CheckSeverity.PASS, "OK"))
        self.assertEqual(report.overall, CheckSeverity.PASS)

        report.checks.append(CheckResult("Test2", CheckSeverity.WARNING, "Warn"))
        self.assertEqual(report.overall, CheckSeverity.WARNING)

        report.checks.append(CheckResult("Test3", CheckSeverity.ERROR, "Err"))
        self.assertEqual(report.overall, CheckSeverity.ERROR)

    def test_compatibility_grade(self):
        # Clean report -> A
        clean = CompatibilityReport()
        clean.checks.append(CheckResult("c", CheckSeverity.PASS, "ok"))
        self.assertEqual(clean.grade, "A")

        # One warning -> B, three warnings -> C
        one_warn = CompatibilityReport()
        one_warn.checks.append(CheckResult("c", CheckSeverity.WARNING, "w"))
        self.assertEqual(one_warn.grade, "B")
        three_warn = CompatibilityReport()
        for _ in range(3):
            three_warn.checks.append(CheckResult("c", CheckSeverity.WARNING, "w"))
        self.assertEqual(three_warn.grade, "C")

        # One error -> D, two errors -> F
        one_err = CompatibilityReport()
        one_err.checks.append(CheckResult("c", CheckSeverity.ERROR, "e"))
        self.assertEqual(one_err.grade, "D")
        two_err = CompatibilityReport()
        for _ in range(2):
            two_err.checks.append(CheckResult("c", CheckSeverity.ERROR, "e"))
        self.assertEqual(two_err.grade, "F")

    def test_run_namcap_missing(self):
        tools = ToolPaths(namcap="")
        res = _run_namcap(None, tools)
        self.assertEqual(res.severity, CheckSeverity.WARNING)
        self.assertIn("namcap bulunamadı", res.message)

    def test_check_file_conflicts_empty(self):
        tools = ToolPaths()
        res = _check_file_conflicts([], tools)
        self.assertEqual(res.severity, CheckSeverity.PASS)
        self.assertIn("boş", res.message)


if __name__ == "__main__":
    unittest.main()
