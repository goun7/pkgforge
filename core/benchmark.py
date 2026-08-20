"""PkgForge — Performance Benchmark.

Measures conversion speed, memory usage, and delta savings to help
users understand performance characteristics and detect regressions.

Usage:
    pkgforge benchmark                    # Run all benchmarks
    pkgforge benchmark --file test.deb    # Benchmark specific file
    pkgforge benchmark --quick            # Quick mode (skip heavy tests)
"""

from __future__ import annotations

import logging
import os
import shutil

log = logging.getLogger(__name__)
import tempfile
import time
from core.security import safe_run
from dataclasses import dataclass, field
from pathlib import Path

from config import ToolPaths, discover_tools


@dataclass
class BenchmarkResult:
    """Result of a single benchmark measurement."""

    name: str = ""
    duration_ms: int = 0
    memory_peak_kb: int = 0
    input_size_bytes: int = 0
    output_size_bytes: int = 0
    details: str = ""
    passed: bool = True


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""

    results: list[BenchmarkResult] = field(default_factory=list)
    total_duration_ms: int = 0

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    def summary(self) -> str:
        lines = [f"{'Test':<35} {'Duration':>10} {'Memory':>10} {'Status'}"]
        lines.append("-" * 70)
        for r in self.results:
            dur = f"{r.duration_ms}ms" if r.duration_ms < 1000 else f"{r.duration_ms/1000:.1f}s"
            mem = f"{r.memory_peak_kb}KB" if r.memory_peak_kb < 1024 else f"{r.memory_peak_kb//1024}MB"
            status = "✅" if r.passed else "❌"
            lines.append(f"{r.name:<35} {dur:>10} {mem:>10} {status}")
        lines.append("-" * 70)
        lines.append(f"{'Toplam':<35} {self.total_duration_ms/1000:.1f}s{'':>4} {'✅' if self.passed else '❌'}")
        return "\n".join(lines)


def _get_memory_usage() -> int:
    """Get current process memory usage in KB."""
    try:
        with open(f"/proc/{os.getpid()}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0


def _create_test_deb(path: Path) -> bool:
    """Create a minimal test DEB for benchmarking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Create data
        data_dir = tmp / "data" / "usr" / "share" / "benchmark-test"
        data_dir.mkdir(parents=True)
        for i in range(100):
            (data_dir / f"file_{i:03d}.txt").write_text(f"Test file {i}\n" * 100)

        # Create control
        ctrl_dir = tmp / "control"
        ctrl_dir.mkdir()
        (ctrl_dir / "control").write_text(
            "Package: benchmark-test\n"
            "Version: 1.0.0\n"
            "Architecture: amd64\n"
            "Maintainer: PkgForge Benchmark\n"
            "Description: Benchmark test package\n"
            "Installed-Size: 100\n",
        )
        (tmp / "debian-binary").write_text("2.0\n")

        # Create tars
        safe_run(["tar", "czf", str(tmp / "control.tar.gz"), "-C", str(ctrl_dir), "control"])
        safe_run(["tar", "czf", str(tmp / "data.tar.gz"), "-C", str(tmp), "data"])

        # Assemble .deb
        result = safe_run(
            ["ar", "rcs", str(path),
             str(tmp / "debian-binary"),
             str(tmp / "control.tar.gz"),
             str(tmp / "data.tar.gz")],
        )
        return result.returncode == 0


def run_benchmarks(
    test_file: Path | None = None,
    quick: bool = False,
) -> BenchmarkReport:
    """Run all benchmarks and return results."""
    report = BenchmarkReport()
    tools = discover_tools()
    start_time = time.monotonic()

    # Benchmark 1: File creation speed
    r = BenchmarkResult(name="Test DEB oluşturma")
    mem_start = _get_memory_usage()
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as tmpdir:
        deb_path = Path(tmpdir) / "test_1.0.0_amd64.deb"
        ok = _create_test_deb(deb_path)
    r.duration_ms = int((time.monotonic() - t0) * 1000)
    r.memory_peak_kb = _get_memory_usage() - mem_start
    r.passed = ok
    r.details = f"Oluşturulan: {deb_path.name}" if ok else "Başarısız"
    report.results.append(r)

    # Benchmark 2: SHA-256 hash speed
    if test_file and test_file.is_file():
        r = BenchmarkResult(name="SHA-256 hash")
        r.input_size_bytes = test_file.stat().st_size
        mem_start = _get_memory_usage()
        t0 = time.monotonic()
        from core.security import safe_run, sha256_hash
        h = sha256_hash(test_file)
        r.duration_ms = int((time.monotonic() - t0) * 1000)
        r.memory_peak_kb = _get_memory_usage() - mem_start
        r.passed = len(h) == 64
        r.details = f"{r.input_size_bytes / 1024:.0f}KB → {r.duration_ms}ms"
        report.results.append(r)

    # Benchmark 3: MIME type validation
    if test_file and test_file.is_file():
        r = BenchmarkResult(name="MIME type doğrulama")
        mem_start = _get_memory_usage()
        t0 = time.monotonic()
        from core.security import validate_mime_type
        try:
            mime = validate_mime_type(test_file, tools)
            r.passed = True
            r.details = mime
        except ValueError:
            r.passed = False
            r.details = "Geçersiz MIME"
        r.duration_ms = int((time.monotonic() - t0) * 1000)
        r.memory_peak_kb = _get_memory_usage() - mem_start
        report.results.append(r)

    # Benchmark 4: Package analysis
    if test_file and test_file.is_file() and tools.ar:
        r = BenchmarkResult(name="Paket analizi")
        mem_start = _get_memory_usage()
        t0 = time.monotonic()
        from core.package_analyzer import analyze_package
        try:
            meta = analyze_package(test_file, tools)
            r.passed = bool(meta.name)
            r.details = f"{meta.name} {meta.version}"
        except Exception as exc:
            r.passed = False
            r.details = str(exc)[:50]
        r.duration_ms = int((time.monotonic() - t0) * 1000)
        r.memory_peak_kb = _get_memory_usage() - mem_start
        report.results.append(r)

    # Benchmark 5: Security checks
    if test_file and test_file.is_file():
        r = BenchmarkResult(name="Güvenlik kontrolleri (tümü)")
        mem_start = _get_memory_usage()
        t0 = time.monotonic()
        from core.security import (
            validate_file_size, sha256_hash, check_path_traversal, check_compression_bomb,
        )
        validate_file_size(test_file, 2048, 500)
        sha256_hash(test_file)
        check_path_traversal(["usr/bin/app", "etc/config.conf"])
        check_compression_bomb(test_file, tools)
        r.duration_ms = int((time.monotonic() - t0) * 1000)
        r.memory_peak_kb = _get_memory_usage() - mem_start
        r.passed = True
        r.details = f"{r.duration_ms}ms toplam"
        report.results.append(r)

    # Benchmark 6: xdelta3 delta creation (if available)
    if not quick and shutil.which("xdelta3") and test_file and test_file.is_file():
        r = BenchmarkResult(name="xdelta3 delta oluşturma")
        with tempfile.TemporaryDirectory() as tmpdir:
            old_file = Path(tmpdir) / "old.bin"
            new_file = Path(tmpdir) / "new.bin"
            delta_file = Path(tmpdir) / "delta.xdelta"

            # Create similar files (small diff)
            old_data = test_file.read_bytes()
            new_data = old_data[:-100] + b"\x00" * 100

            old_file.write_bytes(old_data)
            new_file.write_bytes(new_data)

            mem_start = _get_memory_usage()
            t0 = time.monotonic()
            from core.delta_updater import create_delta
            ok = create_delta(old_file, new_file, delta_file)
            r.duration_ms = int((time.monotonic() - t0) * 1000)
            r.memory_peak_kb = _get_memory_usage() - mem_start
            r.input_size_bytes = len(new_data)
            r.output_size_bytes = delta_file.stat().st_size if delta_file.exists() else 0
            r.passed = ok
            if ok:
                ratio = (1 - r.output_size_bytes / r.input_size_bytes) * 100 if r.input_size_bytes > 0 else 0
                r.details = f"{r.output_size_bytes / 1024:.0f}KB delta, {ratio:.0f}% tasarruf"
        report.results.append(r)

    # Benchmark 7: Provenance generation
    r = BenchmarkResult(name="Provenance oluşturma")
    mem_start = _get_memory_usage()
    t0 = time.monotonic()
    from core.provenance import create_provenance
    prov = create_provenance(source_file="/tmp/test.deb", package_name="test")
    r.duration_ms = int((time.monotonic() - t0) * 1000)
    r.memory_peak_kb = _get_memory_usage() - mem_start
    r.passed = bool(prov.provenance_hash)
    r.details = f"Hash: {prov.provenance_hash[:16]}…"
    report.results.append(r)

    report.total_duration_ms = int((time.monotonic() - start_time) * 1000)
    return report
