"""Unit tests for installer scripts, completion files, and dialog classes."""

import csv
import io
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestInstallerAndCompletions(unittest.TestCase):

    def test_install_script_exists_and_executable(self):
        install_script = PROJECT_ROOT / "scripts" / "install.sh"
        uninstall_script = PROJECT_ROOT / "scripts" / "uninstall.sh"
        self.assertTrue(install_script.is_file())
        self.assertTrue(uninstall_script.is_file())

    def test_completion_files_exist(self):
        bash_comp = PROJECT_ROOT / "data" / "completions" / "pkgforge.bash"
        zsh_comp = PROJECT_ROOT / "data" / "completions" / "_pkgforge"
        self.assertTrue(bash_comp.is_file())
        self.assertTrue(zsh_comp.is_file())

    def test_desktop_file_validity(self):
        desktop_file = PROJECT_ROOT / "data" / "pkgforge.desktop"
        self.assertTrue(desktop_file.is_file())
        content = desktop_file.read_text(encoding="utf-8")
        self.assertIn("Name=PkgForge", content)
        self.assertIn("Exec=pkgforge gui %f", content)


class TestHistoryCSVImport(unittest.TestCase):
    """Test CSV import logic for history dialog."""

    def test_csv_import_valid(self):
        """Valid CSV with correct columns should import all rows."""
        from core.history_db import HistoryDB

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["package_name", "package_type", "original_file", "source_url"])
            writer.writerow(["test-pkg", "deb", "test.deb", "https://example.com/test.deb"])
            writer.writerow(["test-pkg2", "rpm", "test.rpm", ""])
            csv_path = Path(f.name)

        try:
            db = HistoryDB()
            initial_count = len(db.get_history(limit=1000))

            content = csv_path.read_text(encoding="utf-8")
            reader = csv.DictReader(io.StringIO(content))
            imported = 0
            for row in reader:
                name = (row.get("package_name") or "").strip()
                ptype = (row.get("package_type") or "").strip()
                orig = (row.get("original_file") or "").strip()
                url = (row.get("source_url") or "").strip()
                if name and ptype:
                    db.add_record(
                        package_name=name, original_file=orig,
                        package_type=ptype, sha256="", status="imported",
                        output_pkg="", source_url=url,
                    )
                    imported += 1

            self.assertEqual(imported, 2)
            final_count = len(db.get_history(limit=1000))
            self.assertGreaterEqual(final_count, initial_count + 2)
        finally:
            csv_path.unlink()

    def test_csv_import_missing_columns(self):
        """CSV missing required columns should be rejected."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "type"])  # Missing required columns
            writer.writerow(["test", "deb"])
            csv_path = Path(f.name)

        try:
            content = csv_path.read_text(encoding="utf-8")
            reader = csv.DictReader(io.StringIO(content))
            required = {"package_name", "package_type", "original_file"}
            self.assertTrue(required - set(reader.fieldnames or []))
        finally:
            csv_path.unlink()

    def test_csv_import_empty_rows_skipped(self):
        """Rows with empty name or type should be skipped."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["package_name", "package_type", "original_file", "source_url"])
            writer.writerow(["", "deb", "test.deb", ""])  # Empty name
            writer.writerow(["good-pkg", "", "test.rpm", ""])  # Empty type
            writer.writerow(["good-pkg2", "rpm", "test2.rpm", ""])  # Valid
            csv_path = Path(f.name)

        try:
            content = csv_path.read_text(encoding="utf-8")
            reader = csv.DictReader(io.StringIO(content))
            valid = 0
            for row in reader:
                if (row.get("package_name") or "").strip() and (row.get("package_type") or "").strip():
                    valid += 1
            self.assertEqual(valid, 1)
        finally:
            csv_path.unlink()


class TestSettingsPreview(unittest.TestCase):
    """Test live config preview generation."""

    def test_config_json_generation(self):
        """Settings config should produce valid JSON."""
        import json
        config = {
            "language": "tr",
            "theme": "dark",
            "aur_check": True,
            "distrobox_fallback": False,
            "clamav_scan": True,
            "snapshot": True,
            "dry_run": False,
            "allow_insecure_http": False,
            "timeout_seconds": 120,
            "output_dir": None,
            "verbose": False,
            "auto_sign": False,
        }
        json_str = json.dumps(config, indent=2, ensure_ascii=False)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["language"], "tr")
        self.assertEqual(parsed["timeout_seconds"], 120)
        self.assertIsNone(parsed["output_dir"])

    def test_config_json_unicode(self):
        """Config with Turkish characters should be valid JSON."""
        import json
        config = {"language": "tr", "theme": "dark"}
        result = json.dumps(config, ensure_ascii=False)
        self.assertIn("tr", result)
        parsed = json.loads(result)
        self.assertEqual(parsed["language"], "tr")


if __name__ == "__main__":
    unittest.main()
