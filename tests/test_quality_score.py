"""Tests for quality_score: dataclasses + real score_package integration.

Uses the git-tracked lictest .pkg.tar.zst fixture to exercise the full
scoring pipeline (ABI, malware, traversal, deps, arch, metadata, size).
"""

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LICTEST_PKG = PROJECT_ROOT / "utest" / "lictest" / "lictest-1.0.0-1-any.pkg.tar.zst"


class TestQualityReportDataclass(unittest.TestCase):

    def test_empty_report_fails(self):
        from core.quality_score import QualityReport
        r = QualityReport()
        self.assertFalse(r.passed)  # 0 < 60

    def test_passing_report(self):
        from core.quality_score import QualityReport
        r = QualityReport(total_score=75)
        self.assertTrue(r.passed)

    def test_summary_contains_score(self):
        from core.quality_score import QualityCheck, QualityReport
        r = QualityReport(
            package_name="hello", total_score=80, grade="B",
            checks=[QualityCheck(
                name="Test", category="security", passed=True,
                score=10, max_score=10, detail="ok",
            )],
        )
        s = r.summary()
        self.assertIn("hello", s)
        self.assertIn("80", s)
        self.assertIn("SECURITY", s)

    def test_summary_grade_interpretation(self):
        from core.quality_score import QualityReport
        # >= 90 -> production-ready
        self.assertIn("production-ready", QualityReport(total_score=95).summary())
        # < 40 -> not recommended
        self.assertIn("kurulum önerilmez", QualityReport(total_score=10).summary())


class TestNameFromFilename(unittest.TestCase):
    """Regression: score_package used stem.split(".")[0] which mis-parsed
    dotted versions (lictest-1.0.0-1-any -> "lictest-1")."""

    def _name(self, fname):
        from core.quality_score import _name_from_filename
        return _name_from_filename(Path("/tmp") / fname)

    def test_standard(self):
        self.assertEqual(self._name("lictest-1.0.0-1-any.pkg.tar.zst"), "lictest")

    def test_dotted_version(self):
        self.assertEqual(self._name("hello-2.12.1-3-x86_64.pkg.tar.zst"), "hello")

    def test_hyphenated_name(self):
        self.assertEqual(self._name("my-cool-app-1.0-1-x86_64.pkg.tar.zst"), "my-cool-app")

    def test_xz_suffix(self):
        self.assertEqual(self._name("pkg-1.0-1-any.pkg.tar.xz"), "pkg")

    def test_no_suffix(self):
        self.assertEqual(self._name("plainname"), "plainname")


@unittest.skipUnless(LICTEST_PKG.is_file(), "lictest .pkg.tar.zst fixture missing")
class TestReadPkginfo(unittest.TestCase):

    def test_reads_pkginfo(self):
        from core.quality_score import _read_pkginfo
        info = _read_pkginfo(LICTEST_PKG)
        self.assertIsInstance(info, dict)
        # lictest is a real Arch package -> must have pkgname and pkgver
        self.assertEqual(info.get("pkgname"), "lictest")
        self.assertIn("pkgver", info)

    def test_missing_file_returns_empty(self):
        from core.quality_score import _read_pkginfo
        info = _read_pkginfo(Path("/nonexistent/x.pkg.tar.zst"))
        self.assertEqual(info, {})


@unittest.skipUnless(LICTEST_PKG.is_file(), "lictest .pkg.tar.zst fixture missing")
class TestScorePackageIntegration(unittest.TestCase):

    def test_score_real_package(self):
        from config import discover_tools
        from core.quality_score import score_package
        report = score_package(LICTEST_PKG, discover_tools())
        self.assertEqual(report.package_name, "lictest")
        # Must produce checks across all four categories
        categories = {c.category for c in report.checks}
        self.assertIn("security", categories)
        self.assertIn("compatibility", categories)
        self.assertIn("metadata", categories)
        self.assertIn("size", categories)
        # Total score must be within bounds and consistent with checks
        self.assertGreaterEqual(report.total_score, 0)
        self.assertLessEqual(report.total_score, report.max_score)
        self.assertEqual(
            report.total_score, sum(c.score for c in report.checks)
        )
        # A valid, clean test package should score reasonably well
        self.assertGreaterEqual(report.total_score, 40)

    def test_summary_renders(self):
        from config import discover_tools
        from core.quality_score import score_package
        report = score_package(LICTEST_PKG, discover_tools())
        s = report.summary()
        self.assertIn("lictest", s)


if __name__ == "__main__":
    unittest.main()
