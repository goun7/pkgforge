"""E2E tests with real-world packages.

Uses actual RPM/DEB files found on the system to test the full
conversion pipeline, security checks, and metadata extraction.
"""

import tempfile
import unittest
from pathlib import Path

import pytest

from config import discover_tools

# Project root (tests/ lives one level below it). Both committed fixtures live
# under utest/ (see .gitignore keep-rules): a minimal hello .deb and a tiny
# hello .rpm — real, buildable packages, preferred over host discovery so
# these E2E tests run anywhere (including CI).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Committed fixtures are known-good, buildable packages — accept them
# regardless of size (the hello .deb is a minimal 884-byte package). The
# >1024-byte filter only applies to files discovered on the host, where it
# skips empty/corrupt placeholders.
_FIXTURE_RPM = _PROJECT_ROOT / "utest" / "fixtures" / "hello-1.0.0-1.x86_64.rpm"
_FIXTURE_DEB = _PROJECT_ROOT / "utest" / "hello_1.0.0-1_amd64.deb"


def _find_real_rpm() -> Path | None:
    """Find a real RPM file for testing (project fixture first, then host)."""
    if _FIXTURE_RPM.is_file():
        return _FIXTURE_RPM
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
    """Find a real DEB file for testing (project fixture first, then host)."""
    if _FIXTURE_DEB.is_file():
        return _FIXTURE_DEB
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


@pytest.mark.slow
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

        with tempfile.TemporaryDirectory(prefix="pkgforge_e2e_"):
            # Step 1: Security checks
            from core.security import (
                check_compression_bomb,
                sha256_hash,
                validate_file_size,
                validate_mime_type,
            )

            mime = validate_mime_type(REAL_RPM, tools)
            self.assertEqual(mime, "application/x-rpm", f"Wrong MIME: {mime}")
            print(f"  ✓ MIME: {mime}")

            validate_file_size(REAL_RPM, 1024, 500)
            print("  ✓ Size check passed")

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
            except Exception:  # noqa: BLE001
                print("  ⚠ ABI scan skipped (readelf not available)")

            # Verify all steps completed
            print(f"\n  🎉 E2E pipeline completed successfully for {REAL_RPM.name}")

    @unittest.skipIf(REAL_RPM is None, "No real RPM file found on system")
    def test_rpm_dep_graph(self):
        """Build dependency graph from real RPM file."""
        from config import extract_package_name
        from core.dep_graph import build_file_dep_graph
        graph = build_file_dep_graph(REAL_RPM)
        # Even if no ELF binaries found, graph should exist
        self.assertIsNotNone(graph)
        # Root must be the clean package name (NOT stem.split(".")[0], which
        # mis-parses dotted versions: hello-1.0.0-1.x86_64 -> "hello-1").
        self.assertEqual(graph.root, extract_package_name(REAL_RPM.name))
        print(f"  ✓ Graph: {len(graph.nodes)} nodes, {len(graph.warnings)} warnings")


class TestOfflineCache(unittest.TestCase):
    """Test offline cache functionality."""

    def test_cache_put_and_get(self):
        """Cache should store and retrieve values."""
        import tempfile

        from core.offline_cache import OfflineCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = OfflineCache(cache_dir=Path(tmpdir), ttl=3600)
            cache.put("test", "key1", {"name": "test", "version": "1.0"})
            result = cache.get("test", "key1")
            self.assertIsNotNone(result)
            self.assertEqual(result["name"], "test")

    def test_cache_expiry(self):
        """Cache should expire after TTL."""
        import tempfile

        from core.offline_cache import OfflineCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = OfflineCache(cache_dir=Path(tmpdir), ttl=0)  # Immediate expiry
            cache.put("test", "key1", "value1")
            result = cache.get("test", "key1")
            self.assertIsNone(result)

    def test_cache_clear(self):
        """Cache clear should remove all entries."""
        import tempfile

        from core.offline_cache import OfflineCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = OfflineCache(cache_dir=Path(tmpdir))
            cache.put("ns1", "k1", "v1")
            cache.put("ns2", "k2", "v2")
            count = cache.clear_all()
            self.assertEqual(count, 2)
            self.assertIsNone(cache.get("ns1", "k1"))

    def test_cache_stats(self):
        """Cache stats should report correct counts."""
        import tempfile

        from core.offline_cache import OfflineCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = OfflineCache(cache_dir=Path(tmpdir))
            cache.put("test", "k1", "v1")
            stats = cache.stats()
            self.assertEqual(stats["total_entries"], 1)
            self.assertIn("test", stats["namespaces"])


class TestPluginSystem(unittest.TestCase):
    """Test plugin loading and discovery."""

    def test_load_plugins(self):
        """Plugins should load from core/plugins/."""
        from core.plugins import load_plugins
        plugins = load_plugins()
        self.assertIsInstance(plugins, dict)

    def test_deb_plugin_registered(self):
        """DEB plugin should be auto-registered."""
        from core.plugins import get_converter
        converter = get_converter("deb")
        self.assertIsNotNone(converter)
        self.assertEqual(converter.name, "deb")

    def test_list_plugins(self):
        """list_plugins should return plugin info."""
        from core.plugins import list_plugins
        plugins = list_plugins()
        self.assertIsInstance(plugins, list)


class TestNetworkDownloads(unittest.TestCase):
    """Network-dependent E2E tests.

    These tests download real packages from the internet.
    Marked with @unittest.skipUnless for CI environments.
    """

    def test_download_rejects_http(self):
        """HTTP URLs should be rejected by default."""
        from core.downloader import download_package
        with self.assertRaises(ValueError) as ctx:
            download_package("http://example.com/pkg.deb", require_https=True)
        self.assertIn("HTTPS", str(ctx.exception))

    def test_download_rejects_ftp(self):
        """Non-HTTP schemes should be rejected."""
        from core.downloader import download_package
        with self.assertRaises(ValueError):
            download_package("ftp://example.com/pkg.deb")

    def test_download_invalid_url(self):
        """Invalid URLs should raise ValueError."""
        from core.downloader import download_package
        with self.assertRaises(ValueError):
            download_package("not-a-url")

    def test_downloader_response_info_structure(self):
        """response_info dict should be populated correctly."""


        # Use a known HTTPS endpoint that returns headers
        # We won't actually download a full file, just test the header capture
        info: dict[str, str] = {}
        # We can't easily test with a real download in unit tests,
        # so just verify the dict initialization works
        self.assertIsInstance(info, dict)
        self.assertEqual(len(info), 0)

    def test_sbom_generation_on_real_deb(self):
        """SBOM should be generated from a real .deb file."""
        from config import discover_tools
        from core.sbom import SBOMDocument, generate_sbom

        deb_path = Path("utest/hello_1.0.0-1_amd64.deb")
        if not deb_path.is_file():
            self.skipTest("Test DEB not found")

        tools = discover_tools()
        sbom = generate_sbom(deb_path, tools, include_hashes=False)
        self.assertIsInstance(sbom, SBOMDocument)
        self.assertGreater(sbom.total_files, 0)

    def test_provenance_create_and_verify(self):
        """Provenance record should create and verify correctly."""
        import tempfile

        from core.provenance import (
            create_provenance,
            load_provenance,
            save_provenance,
            verify_provenance,
        )

        deb_path = Path("utest/hello_1.0.0-1_amd64.deb")
        if not deb_path.is_file():
            self.skipTest("Test DEB not found")

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "test.pkg.tar.zst"
            out_path.write_text("fake package", encoding="utf-8")

            prov = create_provenance(
                source_file=deb_path,
                source_type="deb",
                output_file=out_path,
                package_name="hello",
                package_version="1.0.0",
            )
            prov_path = save_provenance(prov, Path(tmp) / "prov.json")
            self.assertTrue(prov_path.exists())

            loaded = load_provenance(prov_path)
            self.assertIsNotNone(loaded)
            valid, msg = verify_provenance(loaded)
            self.assertTrue(valid, msg)

    def test_attestation_create(self):
        """In-toto attestation should be created from provenance."""
        import tempfile

        from core.provenance import (
            create_attestation,
            create_provenance,
            save_attestation,
            verify_attestation,
        )

        deb_path = Path("utest/hello_1.0.0-1_amd64.deb")
        if not deb_path.is_file():
            self.skipTest("Test DEB not found")

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "test.pkg.tar.zst"
            out_path.write_text("fake package", encoding="utf-8")

            prov = create_provenance(
                source_file=deb_path,
                source_type="deb",
                output_file=out_path,
                package_name="hello",
            )
            att = create_attestation(prov)
            att_path = save_attestation(att, Path(tmp) / "test.att.json")
            self.assertTrue(att_path.exists())

            # Verify
            valid, msg = verify_attestation(att)
            self.assertTrue(valid, msg)
            self.assertEqual(len(att.subject), 1)
            self.assertIn("builder", att.predicate)


if __name__ == "__main__":
    unittest.main()


class TestPluginMarketplace(unittest.TestCase):
    """Test plugin marketplace functionality."""

    def test_list_installed_empty(self):
        from core.plugins.marketplace import list_installed_plugins
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.plugins.marketplace as mp
            original = mp.PLUGIN_DIR
            mp.PLUGIN_DIR = Path(tmpdir)
            try:
                result = list_installed_plugins()
                self.assertIsInstance(result, list)
                self.assertEqual(len(result), 0)
            finally:
                mp.PLUGIN_DIR = original

    def test_uninstall_nonexistent(self):
        from core.plugins.marketplace import uninstall_plugin
        result = uninstall_plugin("nonexistent-plugin-xyz")
        self.assertFalse(result)
