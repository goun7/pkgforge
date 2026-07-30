"""Unit tests for core/report_export.py."""

import json
import unittest

from core.compatibility_checker import (
    CompatibilityReport,
    CheckResult,
    CheckSeverity,
)
from core.report_export import report_to_dict, report_to_json


class TestReportExport(unittest.TestCase):

    def _sample_report(self) -> CompatibilityReport:
        report = CompatibilityReport()
        report.checks.append(CheckResult("Namcap", CheckSeverity.PASS, "OK"))
        report.checks.append(
            CheckResult("Deps", CheckSeverity.WARNING, "1 missing", ["libfoo"])
        )
        return report

    def test_report_to_dict_structure(self):
        report = self._sample_report()
        data = report_to_dict(report, sha256="abc123")
        self.assertEqual(data["tool"], "PkgForge")
        self.assertEqual(data["grade"], "B")  # one warning -> B
        self.assertEqual(data["overall"], "warning")
        self.assertEqual(data["sha256"], "abc123")
        self.assertEqual(len(data["checks"]), 2)
        self.assertEqual(data["checks"][1]["details"], ["libfoo"])

    def test_report_to_json_roundtrip(self):
        report = self._sample_report()
        text = report_to_json(report)
        parsed = json.loads(text)  # must be valid JSON
        self.assertEqual(parsed["grade"], "B")
        self.assertIn("generated_at", parsed)

    def test_report_to_dict_none_report(self):
        data = report_to_dict(None)
        self.assertEqual(data["grade"], "N/A")
        self.assertEqual(data["overall"], "unknown")
        self.assertEqual(data["checks"], [])


if __name__ == "__main__":
    unittest.main()
