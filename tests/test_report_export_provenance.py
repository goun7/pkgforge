"""Tests for report_export and provenance round-trip/verification.

All hermetic: in-memory reports and temp files only.
"""

import json
import tempfile
import unittest
from pathlib import Path


class TestReportExport(unittest.TestCase):

    def _report(self):
        from core.compatibility_checker import (
            CheckResult,
            CheckSeverity,
            CompatibilityReport,
        )
        return CompatibilityReport(checks=[
            CheckResult(name="deps", severity=CheckSeverity.PASS, message="ok"),
            CheckResult(name="libs", severity=CheckSeverity.WARNING,
                        message="missing", details=["libfoo.so.1"]),
        ])

    def test_report_to_dict(self):
        from core.report_export import report_to_dict
        d = report_to_dict(self._report(), sha256="ab" * 32)
        self.assertEqual(d["grade"], "B")  # 1 warning -> B
        self.assertEqual(d["overall"], "warning")
        self.assertEqual(d["sha256"], "ab" * 32)
        self.assertEqual(len(d["checks"]), 2)
        self.assertEqual(d["checks"][1]["severity"], "warning")
        self.assertEqual(d["checks"][1]["details"], ["libfoo.so.1"])

    def test_report_to_dict_none(self):
        from core.report_export import report_to_dict
        d = report_to_dict(None)
        self.assertEqual(d["grade"], "N/A")
        self.assertEqual(d["overall"], "unknown")
        self.assertEqual(d["checks"], [])

    def test_report_to_json_valid(self):
        from core.report_export import report_to_json
        s = report_to_json(self._report())
        data = json.loads(s)  # must be valid JSON
        self.assertEqual(data["grade"], "B")

    def test_save_report_json(self):
        from core.report_export import save_report_json
        with tempfile.TemporaryDirectory() as td:
            out = save_report_json(Path(td) / "report.json", self._report())
            self.assertTrue(out.is_file())
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["grade"], "B")


class TestProvenance(unittest.TestCase):

    def test_finalize_and_verify(self):
        from core.provenance import BuildProvenance, verify_provenance
        prov = BuildProvenance(
            source_file="hello.deb", source_type="deb",
            package_name="hello", package_version="1.0.0",
        )
        prov.finalize()
        self.assertTrue(prov.provenance_hash)
        valid, msg = verify_provenance(prov)
        self.assertTrue(valid, msg)

    def test_tampered_hash_fails(self):
        from core.provenance import BuildProvenance, verify_provenance
        prov = BuildProvenance(package_name="hello")
        prov.finalize()
        prov.package_name = "evil"  # tamper after finalize
        valid, _ = verify_provenance(prov)
        self.assertFalse(valid)

    def test_save_load_roundtrip(self):
        from core.provenance import (
            BuildProvenance,
            load_provenance,
            save_provenance,
        )
        with tempfile.TemporaryDirectory() as td:
            prov = BuildProvenance(package_name="hello", package_version="1.0")
            prov.finalize()
            path = save_provenance(prov, Path(td) / "p.provenance.json")
            loaded = load_provenance(path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.package_name, "hello")
            self.assertEqual(loaded.provenance_hash, prov.provenance_hash)

    def test_load_missing_returns_none(self):
        from core.provenance import load_provenance
        self.assertIsNone(load_provenance(Path("/nonexistent/x.json")))

    def test_load_corrupt_returns_none(self):
        from core.provenance import load_provenance
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            f.write("not json {{{")
            path = Path(f.name)
        try:
            self.assertIsNone(load_provenance(path))
        finally:
            path.unlink(missing_ok=True)

    def test_find_provenance(self):
        from core.provenance import find_provenance
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "hello-1.0-1-x86_64.pkg.tar.zst"
            pkg.write_bytes(b"x")
            prov = Path(td) / (pkg.name + ".provenance.json")
            prov.write_text("{}")
            self.assertEqual(find_provenance(pkg), prov)

    def test_find_provenance_missing(self):
        from core.provenance import find_provenance
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "hello.pkg.tar.zst"
            pkg.write_bytes(b"x")
            self.assertIsNone(find_provenance(pkg))


if __name__ == "__main__":
    unittest.main()
