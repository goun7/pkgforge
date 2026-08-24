"""Coverage itmesi — core/benchmark.py (gercek olcum akisi)."""
from __future__ import annotations

import pytest

from config import discover_tools
from core.benchmark import (
    BenchmarkReport,
    BenchmarkResult,
    _create_test_deb,
    _get_memory_usage,
    run_benchmarks,
)


def test_get_memory_usage_returns_kb():
    kb = _get_memory_usage()
    assert isinstance(kb, int)
    assert kb >= 0


def test_create_test_deb_builds_valid_archive(tmp_path):
    deb = tmp_path / "test_1.0.0_amd64.deb"
    assert _create_test_deb(deb) is True
    assert deb.is_file()
    assert deb.stat().st_size > 1000


def test_run_benchmarks_end_to_end(tmp_path):
    deb = tmp_path / "test_1.0.0_amd64.deb"
    assert _create_test_deb(deb)
    tools = discover_tools()
    if not tools.ar:
        pytest.skip("ar yok")
    report = run_benchmarks(test_file=deb, quick=True)
    names = [r.name for r in report.results]
    assert "Test DEB olusturma" in names or any("DEB" in n for n in names)
    assert report.results[0].passed is True
    assert report.total_duration_ms >= 0
    assert report.passed is True, str(
        [(r.name, r.details) for r in report.results if not r.passed])


def test_report_summary_table():
    rep = BenchmarkReport()
    rep.results.append(BenchmarkResult(name="a", duration_ms=10))
    rep.results.append(BenchmarkResult(name="b", duration_ms=1500,
                                       memory_peak_kb=2048, passed=False))
    s = rep.summary()
    assert "a" in s and "b" in s
    assert "1.5s" in s and "2MB" in s
    assert chr(10060) in s and chr(9989) in s
    assert rep.passed is False
