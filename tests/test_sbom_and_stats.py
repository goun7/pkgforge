"""Unit tests for core/sbom.py and core/history_db.py usage stats."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from config import ToolPaths
from core.history_db import HistoryDB
from core.sbom import SBOMDocument, SBOMEntry, generate_sbom, save_sbom


class TestSBOMDocument(unittest.TestCase):
    """Tests for the SBOMDocument dataclass and helpers."""

    def test_summary_empty(self):
        doc = SBOMDocument()
        summary = doc.summary()
        self.assertIn("Toplam", summary)
        self.assertIn("0 dosya", summary)

    def test_summary_with_data(self):
        doc = SBOMDocument()
        doc.package_name = "my-app"
        doc.package_version = "1.2.3"
        doc.package_arch = "x86_64"
        doc.total_files = 120
        doc.total_size_bytes = 5_000_000
        doc.elf_count = 8
        doc.text_count = 30
        doc.symlink_count = 12
        doc.dir_count = 70
        doc.dependencies = ["glibc", "mesa", "openssl"]
        summary = doc.summary()
        self.assertIn("my-app", summary)
        self.assertIn("120 dosya", summary)
        self.assertIn("KB", summary)
        self.assertIn("glibc", summary)

    def test_to_dict_structure(self):
        doc = SBOMDocument()
        doc.package_name = "test"
        doc.files.append(SBOMEntry(path="/usr/bin/app", file_type="elf", sha256="abc", size_bytes=1024))
        d = doc.to_dict()
        self.assertEqual(d["package_name"], "test")
        self.assertEqual(len(d["files"]), 1)
        self.assertEqual(d["files"][0]["path"], "/usr/bin/app")
        self.assertIn("total_files", d)
        self.assertIn("dependencies", d)

    def test_entry_defaults(self):
        entry = SBOMEntry(path="/test")
        self.assertEqual(entry.file_type, "")
        self.assertEqual(entry.sha256, "")
        self.assertEqual(entry.size_bytes, 0)


class TestSBOMSave(unittest.TestCase):
    """Tests for save_sbom file I/O."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pkgforge_sbom_test_")
        self.tmp_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_load(self):
        doc = SBOMDocument()
        doc.document_name = "test-sbom"
        doc.package_name = "demo"
        doc.files.append(SBOMEntry(path="/usr/bin/demo", file_type="elf"))

        out = self.tmp_dir / "test.spdx.json"
        saved = save_sbom(doc, out)
        self.assertTrue(saved.exists())

        loaded = json.loads(saved.read_text(encoding="utf-8"))
        self.assertEqual(loaded["package_name"], "demo")
        self.assertEqual(len(loaded["files"]), 1)

    def test_save_creates_parent_dirs(self):
        doc = SBOMDocument()
        out = self.tmp_dir / "sub" / "dir" / "sbom.json"
        save_sbom(doc, out)
        self.assertTrue(out.exists())


class TestHistoryDBUsageStats(unittest.TestCase):
    """Tests for HistoryDB.get_usage_stats()."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pkgforge_stats_test_")
        self.tmp_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_db(self) -> HistoryDB:
        return HistoryDB(self.tmp_dir / "stats.db")

    def test_empty_db(self):
        db = self._make_db()
        stats = db.get_usage_stats()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["by_status"], {})
        self.assertEqual(stats["by_type"], {})
        self.assertEqual(stats["url_count"], 0)
        self.assertEqual(stats["avg_output_size_mb"], 0.0)

    def test_single_record(self):
        db = self._make_db()
        db.add_record(
            package_name="hello",
            original_file="hello.deb",
            package_type="deb",
            sha256="abc",
            status="converted",
        )
        stats = db.get_usage_stats()
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["by_status"]["converted"], 1)
        self.assertEqual(stats["by_type"]["deb"], 1)
        self.assertTrue(stats["first_seen"])
        self.assertTrue(stats["last_seen"])

    def test_multiple_records(self):
        db = self._make_db()
        for i in range(5):
            ptype = "deb" if i % 2 == 0 else "rpm"
            status = "installed" if i < 3 else "install_failed"
            db.add_record(
                package_name=f"pkg-{i}",
                original_file=f"pkg-{i}.{ptype}",
                package_type=ptype,
                sha256=f"hash{i}",
                status=status,
                source_url=f"https://example.com/pkg{i}.{ptype}" if i % 3 == 0 else "",
            )
        stats = db.get_usage_stats()
        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["by_status"]["installed"], 3)
        self.assertEqual(stats["by_status"]["install_failed"], 2)
        self.assertEqual(stats["by_type"]["deb"], 3)
        self.assertEqual(stats["by_type"]["rpm"], 2)
        self.assertGreater(stats["url_count"], 0)

    def test_first_and_last_seen_order(self):
        db = self._make_db()
        db.add_record(
            package_name="first", original_file="f.deb",
            package_type="deb", sha256="a", status="converted",
        )
        db.add_record(
            package_name="second", original_file="s.deb",
            package_type="deb", sha256="b", status="converted",
        )
        stats = db.get_usage_stats()
        self.assertEqual(stats["first_seen"], stats["last_seen"])
        # Both are current_timestamp, so they're the same
        self.assertTrue(stats["first_seen"])


if __name__ == "__main__":
    unittest.main()


# ── extract_package_name tests ──────────────────────────────────
class TestExtractPackageName:
    """Tests for config.extract_package_name."""

    def test_deb_simple(self):
        from config import extract_package_name
        assert extract_package_name("firefox_91.0-1_amd64.deb") == "firefox"

    def test_deb_dotted_name(self):
        from config import extract_package_name
        assert extract_package_name("libssl1.1_1.1.0-1_amd64.deb") == "libssl1.1"

    def test_deb_python(self):
        from config import extract_package_name
        assert extract_package_name("python3-pip_21.0-1_all.deb") == "python3-pip"

    def test_rpm_simple(self):
        from config import extract_package_name
        assert extract_package_name("openssl-1.1.1k-4-x86_64.rpm") == "openssl"

    def test_rpm_fc_release(self):
        from config import extract_package_name
        assert extract_package_name("glibc-2.33-5.fc34.x86_64.rpm") == "glibc"

    def test_rpm_noarch(self):
        from config import extract_package_name
        assert extract_package_name("python3-setuptools-57.0.0-1.noarch.rpm") == "python3-setuptools"

    def test_pkg_tar_zst(self):
        from config import extract_package_name
        assert extract_package_name("neovim-0.9.0-1-x86_64.pkg.tar.zst") == "neovim"

    def test_url_path(self):
        from config import extract_package_name
        url = "https://example.com/deb/firefox_91.0-1_amd64.deb"
        assert extract_package_name(url) == "firefox"

    def test_plain_name(self):
        from config import extract_package_name
        # No extension — returns as-is
        assert extract_package_name("mypackage") == "mypackage"

    def test_rpm_epoch_prefix(self):
        from config import extract_package_name
        assert extract_package_name("1:openssl-1.1.1k-4-x86_64.rpm") == "openssl"

    def test_rpm_arch_by_hyphen(self):
        from config import extract_package_name
        # Arch can be separated by hyphen instead of dot
        assert extract_package_name("openssl-1.1.1k-4-x86_64.rpm") == "openssl"


class TestSBOMDiff(unittest.TestCase):
    """Tests for SBOM diff functionality."""

    def test_diff_shows_added_files(self):
        from core.sbom import SBOMDocument, SBOMEntry, diff_sboms
        old = SBOMDocument(package_name="test", package_version="1.0")
        old.files = [SBOMEntry(path=f"usr/bin/f{i}") for i in range(3)]
        new = SBOMDocument(package_name="test", package_version="2.0")
        new.files = [SBOMEntry(path=f"usr/bin/f{i}") for i in range(1, 4)]
        new.files.append(SBOMEntry(path="usr/bin/new"))
        diff = diff_sboms(old, new)
        self.assertIn("usr/bin/new", diff.added_files)
        self.assertIn("usr/bin/f0", diff.removed_files)

    def test_diff_shows_deps_changes(self):
        from core.sbom import SBOMDocument, diff_sboms
        old = SBOMDocument(package_name="test", dependencies=["liba", "libb"])
        new = SBOMDocument(package_name="test", dependencies=["liba", "libc"])
        diff = diff_sboms(old, new)
        self.assertEqual(diff.added_deps, ["libc"])
        self.assertEqual(diff.removed_deps, ["libb"])

    def test_diff_no_changes(self):
        from core.sbom import SBOMDocument, SBOMEntry, diff_sboms
        sbom = SBOMDocument(package_name="test", package_version="1.0", total_files=3)
        sbom.files = [SBOMEntry(path=f"usr/bin/f{i}") for i in range(3)]
        sbom.dependencies = ["liba"]
        diff = diff_sboms(sbom, sbom)
        self.assertEqual(diff.added_files, [])
        self.assertEqual(diff.removed_files, [])

    def test_save_sbom_diff(self):
        from core.sbom import SBOMDocument, SBOMEntry, diff_sboms, save_sbom_diff
        import tempfile, json
        old = SBOMDocument(package_name="test")
        new = SBOMDocument(package_name="test")
        diff = diff_sboms(old, new)
        with tempfile.TemporaryDirectory() as tmp:
            path = save_sbom_diff(diff, Path(tmp) / "diff.json")
            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertEqual(data["old_name"], "test")
