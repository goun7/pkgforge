"""Faz 5 (F5.26) — perf butcesi: benchmark baseline karsilastirmasi."""
from __future__ import annotations

from core.benchmark import BenchmarkReport, BenchmarkResult
from core.perf_budget import (
    compare,
    load_baseline,
    report_to_baseline,
    save_baseline,
)


def _report(**durations):
    results = [
        BenchmarkResult(name=name, duration_ms=ms, memory_peak_kb=100)
        for name, ms in durations.items()
    ]
    return BenchmarkReport(results=results)


def test_report_to_baseline_shape():
    rep = _report(convert=1000, scan=500)
    b = report_to_baseline(rep)
    assert b["results"]["convert"]["duration_ms"] == 1000
    assert b["results"]["scan"]["duration_ms"] == 500


def test_save_and_load_roundtrip(tmp_path):
    rep = _report(convert=1000)
    path = save_baseline(rep, tmp_path / "base.json")
    loaded = load_baseline(path)
    assert loaded["convert"]["duration_ms"] == 1000


def test_load_missing_returns_empty(tmp_path):
    assert load_baseline(tmp_path / "nope.json") == {}


def test_compare_detects_regression():
    baseline = {"convert": {"duration_ms": 1000, "memory_peak_kb": 100}}
    rep = _report(convert=1300)  # %30 yavaslama
    res = compare(rep, baseline)
    assert res["ok"] is False
    assert len(res["regressions"]) == 1
    assert res["regressions"][0]["delta_pct"] == 30.0


def test_compare_ok_within_budget():
    baseline = {"convert": {"duration_ms": 1000, "memory_peak_kb": 100}}
    rep = _report(convert=1100)  # %10 yavaslama, esik %20
    res = compare(rep, baseline)
    assert res["ok"] is True
    assert res["regressions"] == []


def test_compare_detects_improvement():
    baseline = {"convert": {"duration_ms": 1000, "memory_peak_kb": 100}}
    rep = _report(convert=700)  # %30 hizlanma
    res = compare(rep, baseline)
    assert res["ok"] is True
    assert len(res["improvements"]) == 1


def test_compare_skips_unknown_benchmark():
    baseline = {"other": {"duration_ms": 100, "memory_peak_kb": 1}}
    rep = _report(convert=9999)
    res = compare(rep, baseline)
    assert res["compared"] == 0
    assert res["ok"] is True


def test_compare_custom_threshold():
    baseline = {"convert": {"duration_ms": 1000, "memory_peak_kb": 100}}
    rep = _report(convert=1100)  # %10
    assert compare(rep, baseline, threshold=0.05)["ok"] is False
    assert compare(rep, baseline, threshold=0.20)["ok"] is True
