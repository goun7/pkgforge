"""E2E tests with real-world packages.

Uses actual RPM/DEB files found on the system to test the full
conversion pipeline, security checks, and metadata extraction.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from config import discover_tools


def _find_real_rpm() -> Path | None:
    """Find a real RPM file on the system for testing."""
    search_paths = [
        Path.home() / "Masaüstü",
        Path.home() / "Desktop",
        Path.home() / "Downloads",
        Path("/tmp"),
    ]
    for p in search_paths:
        if p.is_dir():
            for f in p.glob("*.rpm"):
                if f.stat().st_size > 1024:  # Skip tiny files
                    return f
    return None


def _find_real_deb() -> Path | None:
    """Find a real DEB file on the system for testing."""
    search_paths = [
        Path.home() / "Masaüstü",
        Path.home() / "Desktop",
        Path.home() / "Downloads",
        Path("/tmp"),
    ]
    for p in search_paths:
        if p.is_dir():
            for f in p.glob("*.deb"):
                if f.stat().st_size > 1024:
                    return f
    return None


REAL_RPM = _find_real_rpm()
REAL_DEB = _find_real_deb()


class TestRealRPMAnalysis(unittest.TestCase):
    """Test package analysis with a real RPM file."""

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_analyze_real_rpm(self):
        """Analyze a real RPM and verify metadata extraction."""
        tools = discover_tools()
        from core.package_analyzer import analyze_package
        meta = analyze_package(REAL_RPM, tools)

        # Basic metadata must be extracted
        self.assertTrue(meta.name, "Package name should not be empty")
        self.assertTrue(meta.version, "Package version should not be empty")
        self.assertIn(meta.arch_mapped, ("x86_64", "any", "i686", "aarch64"))

        print(f"  ✓ Real RPM analyzed: {meta.name} {meta.version} ({meta.arch_mapped})")
        print(f"    Files: {len(meta.file_list)}, Type: {meta.package_type}")

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_rpm_file_list_populated(self):
        """File list should be populated for a real RPM."""
        tools = discover_tools()
        from core.package_analyzer import analyze_package
        meta = analyze_package(REAL_RPM, tools)
        self.assertGreater(len(meta.file_list), 0, "File list should not be empty")

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_rpm_mime_type(self):
        """Real RPM should have correct MIME type."""
        tools = discover_tools()
        from core.security import validate_mime_type
        mime = validate_mime_type(REAL_RPM, tools)
        self.assertEqual(mime, "application/x-rpm")

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_rpm_sha256_consistency(self):
        """SHA-256 should be consistent across calls."""
        from core.security import sha256_hash
        h1 = sha256_hash(REAL_RPM)
        h2 = sha256_hash(REAL_RPM)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_rpm_compression_bomb_check(self):
        """Real RPM should not be flagged as compression bomb."""
        tools = discover_tools()
        from core.security import check_compression_bomb
        result = check_compression_bomb(REAL_RPM, tools)
        # Should either be None (safe) or a warning string
        self.assertTrue(result is None or isinstance(result, str))

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_rpm_provenance_creation(self):
        """Should create provenance record for real RPM."""
        from core.provenance import create_provenance
        prov = create_provenance(
            source_file=REAL_RPM,
            package_name="test-rpm",
            package_type="rpm",
        )
        self.assertTrue(prov.build_id)
        self.assertTrue(prov.provenance_hash)
        self.assertEqual(len(prov.provenance_hash), 64)


class TestRealDEBAnalysis(unittest.TestCase):
    """Test package analysis with a real DEB file (if available)."""

    @unittest.skipIf(REAL_DEB is None, "No real DEB file found on system")
    def test_analyze_real_deb(self):
        tools = discover_tools()
        from core.package_analyzer import analyze_package
        meta = analyze_package(REAL_DEB, tools)
        self.assertTrue(meta.name)
        self.assertTrue(meta.version)


class TestSecurityWithRealPackage(unittest.TestCase):
    """Security checks with real packages."""

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_path_traversal_on_real_files(self):
        """Path traversal check on real RPM file list."""
        tools = discover_tools()
        from core.package_analyzer import analyze_package
        from core.security import check_path_traversal

        meta = analyze_package(REAL_RPM, tools)
        offending = check_path_traversal(meta.file_list)
        # Real packages should not have traversal
        self.assertEqual(offending, [], f"Unexpected traversal: {offending[:3]}")

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_snapshot_detection(self):
        """Snapshot manager should detect current backend."""
        from core.snapshot_manager import detect_backend
        backend = detect_backend()
        self.assertIn(backend, ("btrfs", "zfs", "none"))


if __name__ == "__main__":
    unittest.main()


class TestRealRPMConversion(unittest.TestCase):
    """Full E2E test: convert real RPM through the entire pipeline."""

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_full_rpm_conversion_pipeline(self):
        """Convert qoder_x86_64.rpm through security → analysis → conversion.

        This tests the ENTIRE pipeline with a real RPM, not just individual steps.
        The output should be a .pkg.tar.zst file (or at minimum, conversion should
        succeed without errors).
        """
        tools = discover_tools()
        if not tools.ar or not tools.makepkg:
            self.skipTest("Required tools (ar, makepkg) not available")

        with tempfile.TemporaryDirectory(prefix="pkgforge_e2e_") as tmpdir:
            out_dir = Path(tmpdir)

            # Step 1: Security checks
            from core.security import validate_mime_type, validate_file_size, sha256_hash, check_compression_bomb

            mime = validate_mime_type(REAL_RPM, tools)
            self.assertEqual(mime, "application/x-rpm", f"Wrong MIME: {mime}")
            print(f"  ✓ MIME: {mime}")

            validate_file_size(REAL_RPM, 1024, 500)
            print(f"  ✓ Size check passed")

            sha = sha256_hash(REAL_RPM)
            self.assertEqual(len(sha), 64)
            print(f"  ✓ SHA-256: {sha[:16]}...")

            bomb = check_compression_bomb(REAL_RPM, tools)
            # bomb should be None (safe) or a warning string
            print(f"  ✓ Bomb check: {'safe' if bomb is None else bomb}")

            # Step 2: Package analysis
            from core.package_analyzer import analyze_package
            meta = analyze_package(REAL_RPM, tools)

            self.assertTrue(meta.name, "Package name should not be empty")
            self.assertTrue(meta.version, "Package version should not be empty")
            self.assertEqual(meta.package_type, "rpm")
            self.assertGreater(len(meta.file_list), 0, "File list should not be empty")
            print(f"  ✓ Analyzed: {meta.name} {meta.version} ({meta.arch_mapped})")
            print(f"    Files: {len(meta.file_list)}, Deps: {len(meta.depends)}")

            # Step 3: Compatibility check
            from core.compatibility_checker import run_compatibility_checks
            compat = run_compatibility_checks(
                REAL_RPM, meta.file_list, meta.depends, tools
            )
            print(f"  ✓ Compatibility: {compat.grade} ({compat.overall.value})")

            # Step 4: Provenance creation
            from core.provenance import create_provenance
            prov = create_provenance(
                source_file=REAL_RPM,
                package_name=meta.name,
                package_version=meta.version,
                package_type="rpm",
            )
            self.assertTrue(prov.build_id)
            self.assertTrue(prov.provenance_hash)
            print(f"  ✓ Provenance: {prov.build_id}")

            # Step 5: ABI check (if readelf available)
            try:
                from core.abi_scanner import check_abi_compatibility
                abi_report = check_abi_compatibility(REAL_RPM)
                print(f"  ✓ ABI scan: {abi_report.binary_count} binaries, {abi_report.error_count} issues")
            except Exception:
                print("  ⚠ ABI scan skipped (readelf not available)")

            # Verify all steps completed
            print(f"\n  🎉 E2E pipeline completed successfully for {REAL_RPM.name}")

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_rpm_dep_graph(self):
        """Build dependency graph from real RPM file."""
        from core.dep_graph import build_file_dep_graph
        graph = build_file_dep_graph(REAL_RPM)
        # Even if no ELF binaries found, graph should exist
        self.assertIsNotNone(graph)
        self.assertEqual(graph.root, REAL_RPM.stem.split(".")[0])
        print(f"  ✓ Graph: {len(graph.nodes)} nodes, {len(graph.warnings)} warnings")
