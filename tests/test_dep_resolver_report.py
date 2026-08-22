"""Tests for dep_resolver.ResolveReport summary rendering.

The pure parsers (_parse_dep_string, soname parsers, is_elf_file) are
already covered in test_low_coverage_pure_logic.py; this adds the report.
"""

import unittest


class TestResolveReportSummary(unittest.TestCase):

    def test_all_resolved(self):
        from core.dep_resolver import DepStatus, ResolveReport
        r = ResolveReport(
            deps=[DepStatus(name="glibc", resolved=True, source="pacman")],
            all_resolved=True, total=1, resolved_count=1, missing_count=0,
        )
        s = r.summary()
        self.assertIn("1", s)
        self.assertNotIn("Eksik ba", s)  # no missing section

    def test_missing_listed(self):
        from core.dep_resolver import DepStatus, ResolveReport
        r = ResolveReport(
            deps=[
                DepStatus(name="glibc", resolved=True, source="pacman"),
                DepStatus(name="libfoo", resolved=False, source="not_found"),
            ],
            all_resolved=False, total=2, resolved_count=1, missing_count=1,
        )
        s = r.summary()
        self.assertIn("libfoo", s)
        self.assertIn("not_found", s)


if __name__ == "__main__":
    unittest.main()
