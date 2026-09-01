"""Tur-55 B6: Performance regression gate.

Bu test gerçek metrikleri ölçer, baseline'la karşılaştırır ve eşik
(default %20) aşıldığında fail eder. Yeni benchmark'lar baseline'a
otomatik eklenir (karşılaştırma dışı), böylece baseline'ı büyütebiliriz.

CI'da `tests/perf_baseline.json` repoya commit edilir; yeni benchmark
ilk çalıştırmada baseline'a eklenir, sonraki çalıştırmalarda karşılaştırılır.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from core.benchmark import BenchmarkReport, BenchmarkResult
from core.perf_budget import (
    DEFAULT_THRESHOLD,
    compare,
    load_baseline,
    save_baseline,
)

REPO = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO / "tests" / "perf_baseline.json"


def _measure_json_serialize_5k() -> float:
    """Stable workload: serialize 5000 small dicts to JSON."""
    payload = {"name": "test-pkg", "version": "1.0.0", "arch": "amd64",
               "deps": ["libc", "glib2"], "size": 1024, "ok": True}
    iterations = 5000
    t0 = time.perf_counter()
    for _ in range(iterations):
        json.dumps(payload)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return elapsed_ms


def _measure_human_formatter_1k() -> float:
    """Stable workload: format 1000 log records through HumanFormatter."""
    from core.structured_log import HumanFormatter
    fmt = HumanFormatter(use_colors=False)
    iterations = 1000
    t0 = time.perf_counter()
    for i in range(iterations):
        rec = _ShimRecord("pkgforge.x.%d" % i, "msg-%d" % i)
        fmt.format(rec)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return elapsed_ms


class _ShimRecord:
    """Minimal LogRecord shim so we don't pull logging in here."""
    def __init__(self, name: str, msg: str) -> None:
        self.name = name
        self.levelname = "INFO"
        self.created = 1700000000.0
        self.module = "x"
        self.funcName = "y"
        self.lineno = 1
        self.message = msg

    def getMessage(self) -> str:
        return self.message


def _collect_report() -> BenchmarkReport:
    """Run the real workload bundle and produce a BenchmarkReport."""
    results = []
    results.append(BenchmarkResult(
        name="json.serialize_5k",
        duration_ms=_measure_json_serialize_5k(),
        memory_peak_kb=0,
    ))
    results.append(BenchmarkResult(
        name="log.human_formatter_1k",
        duration_ms=_measure_human_formatter_1k(),
        memory_peak_kb=0,
    ))
    return BenchmarkReport(results=results)


def test_perf_regression_gate() -> None:
    """Run perf workloads and compare against baseline.

    İlk çalıştırmada baseline yoksa mevcut sonuçlar baseline olarak
    yazılır (regresyon aranmadığı için test geçer) ve 'baseline yazıldı'
    mesajı verilir.

    Sonraki çalıştırmalarda baseline yüklenir; %20'yi aşan yavaşlama
    testin başarısız olmasına neden olur (CI gate).
    """
    report = _collect_report()

    if not BASELINE_PATH.is_file():
        # No baseline yet — save one and pass.
        save_baseline(report, BASELINE_PATH)
        pytest.skip(f"perf baseline yazıldı: {BASELINE_PATH} — sonraki "
                    f"çalıştırmalarda regresyon aranacak.")

    baseline = load_baseline(BASELINE_PATH)
    if not baseline:
        save_baseline(report, BASELINE_PATH)
        pytest.skip("perf baseline boş — yeniden yazıldı.")

    result = compare(report, baseline, threshold=DEFAULT_THRESHOLD)

    # Persist the latest run so devs can refresh baseline by committing.
    save_baseline(report, BASELINE_PATH.with_suffix(".latest.json"))

    if not result["ok"]:
        # Auto-bump baseline when explicitly requested (CI opt-in).
        if os.environ.get("PKGFORGE_REFRESH_BASELINE") == "1":
            save_baseline(report, BASELINE_PATH)
            pytest.skip("regresyon var ama PKGFORGE_REFRESH_BASELINE=1 "
                        "ile baseline güncellendi.")

        details = ", ".join(
            f"{r['name']} +{r['delta_pct']:.1f}%"
            for r in result["regressions"]
        )
        pytest.fail(
            f"perf regresyonu (>{DEFAULT_THRESHOLD*100:.0f}%): {details}. "
            f"Baseline güncellemek için: PKGFORGE_REFRESH_BASELINE=1 "
            f"pytest tests/test_perf_regression_smoke.py"
        )


def test_compare_threshold_is_20pct() -> None:
    """Default regression threshold must be 20% (F5.26 spec)."""
    assert DEFAULT_THRESHOLD == 0.20


def test_load_baseline_handles_corrupt(tmp_path) -> None:
    """Corrupt baseline must not crash, must return empty."""
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert load_baseline(p) == {}
