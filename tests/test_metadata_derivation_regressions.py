"""Regression tests for filename-derived metadata bugs.

F33: history_db.get_usage_stats inferred arch as "x86_64.pkg.tar" because
     .stem leaves the ".pkg.tar" chain glued to the arch segment.
F34: oci_builder.build_oci_image derived the OCI tag from the raw stem,
     producing "pkgforge/hello-1.0.0-1-x86_64.pkg.tar:latest" instead of
     "pkgforge/hello:latest".
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestHistoryStatsArch(unittest.TestCase):
    """get_usage_stats must bucket by the clean arch, not ".pkg.tar" glue."""

    def test_arch_inferred_without_pkg_tar_suffix(self):
        from core.history_db import HistoryDB

        with tempfile.TemporaryDirectory() as td:
            db = HistoryDB(db_path=Path(td) / "hist.db")
            # Create a real output file so stat() succeeds and arch is parsed.
            out = Path(td) / "hello-1.0.0-1-x86_64.pkg.tar.zst"
            out.write_bytes(b"x" * 1024)
            db.add_record(
                package_name="hello",
                original_file="hello.deb",
                package_type="deb",
                sha256="a" * 64,
                status="success",
                output_pkg=str(out),
            )
            stats = db.get_usage_stats()
            # Must be the clean arch, NOT "x86_64.pkg.tar" (the old bug).
            self.assertIn("x86_64", stats["by_arch"])
            self.assertNotIn("x86_64.pkg.tar", stats["by_arch"])
            self.assertEqual(stats["by_arch"]["x86_64"], 1)

    def test_arch_any_variant(self):
        from core.history_db import HistoryDB

        with tempfile.TemporaryDirectory() as td:
            db = HistoryDB(db_path=Path(td) / "hist.db")
            out = Path(td) / "lictest-1.0.0-1-any.pkg.tar.zst"
            out.write_bytes(b"x")
            db.add_record(
                package_name="lictest",
                original_file="lictest.deb",
                package_type="deb",
                sha256="b" * 64,
                status="success",
                output_pkg=str(out),
            )
            stats = db.get_usage_stats()
            self.assertIn("any", stats["by_arch"])
            self.assertNotIn("any.pkg.tar", stats["by_arch"])


class TestOciTagDerivation(unittest.TestCase):
    """build_oci_image must tag with the clean package name."""

    def test_tag_is_clean_name(self):
        from config import discover_tools
        from core import oci_builder

        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "hello-1.0.0-1-x86_64.pkg.tar.zst"
            pkg.write_bytes(b"x")
            captured = {}

            def fake_buildah(pkg_path, buildah_bin, tag, output_file):
                captured["tag"] = tag
                return True, "ok", output_file

            with patch.object(oci_builder.shutil, "which", return_value="/usr/bin/buildah"), \
                 patch.object(oci_builder, "_build_with_buildah", side_effect=fake_buildah):
                ok, _msg, _out = oci_builder.build_oci_image(pkg, discover_tools())
            self.assertTrue(ok)
            # Must be the clean name, NOT the raw stem with .pkg.tar glued on.
            self.assertEqual(captured["tag"], "pkgforge/hello:latest")
            self.assertNotIn(".pkg.tar", captured["tag"])

    def test_tag_hyphenated_name(self):
        from config import discover_tools
        from core import oci_builder

        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "my-cool-app-1.2.3-4-x86_64.pkg.tar.zst"
            pkg.write_bytes(b"x")
            captured = {}

            def fake_buildah(pkg_path, buildah_bin, tag, output_file):
                captured["tag"] = tag
                return True, "ok", output_file

            with patch.object(oci_builder.shutil, "which", return_value="/usr/bin/buildah"), \
                 patch.object(oci_builder, "_build_with_buildah", side_effect=fake_buildah):
                ok, _msg, _out = oci_builder.build_oci_image(pkg, discover_tools())
            self.assertTrue(ok)
            self.assertEqual(captured["tag"], "pkgforge/my-cool-app:latest")


if __name__ == "__main__":
    unittest.main()
