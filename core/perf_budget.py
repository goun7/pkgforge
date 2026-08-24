"""Faz 5 (F5.26) — perf butcesi: benchmark baseline karsilastirmasi.

Bir onceki calistirmadan kaydedilen baseline'a gore mevcut benchmark
sonuclarini karsilastirir. Bir metrik esikten (varsayilan %20) fazla
yavasladiysa bu bir regresyondur ve rapor 'ok=False' doner. Iyilesmeler
bilgi olarak listelenir, asla basarisiz sayilmaz.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DEFAULT_THRESHOLD = 0.20  # %20 yavaslama = regresyon


def report_to_baseline(report: Any) -> dict[str, Any]:
    """Serialize a BenchmarkReport into the baseline JSON shape."""
    results: dict[str, Any] = {}
    for r in getattr(report, "results", []):
        results[r.name] = {
            "duration_ms": int(r.duration_ms),
            "memory_peak_kb": int(r.memory_peak_kb),
        }
    return {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "results": results,
    }


def save_baseline(report: Any, path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report_to_baseline(report), indent=2),
                   encoding="utf-8")
    return out


def load_baseline(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        results = data.get("results", {})
        return results if isinstance(results, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def compare(report: Any, baseline: dict[str, Any],
            threshold: float = DEFAULT_THRESHOLD) -> dict[str, Any]:
    """Compare a BenchmarkReport against a baseline.

    Returns a dict with ok/threshold/compared/regressions/improvements.
    A benchmark with no baseline entry is skipped (not a regression).
    """
    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    compared = 0
    for r in getattr(report, "results", []):
        base = baseline.get(r.name)
        if not isinstance(base, dict):
            continue
        base_ms = float(base.get("duration_ms", 0))
        if base_ms <= 0:
            continue
        compared += 1
        delta_pct = (float(r.duration_ms) - base_ms) / base_ms
        entry = {
            "name": r.name,
            "current_ms": int(r.duration_ms),
            "baseline_ms": int(base_ms),
            "delta_pct": round(delta_pct * 100, 1),
        }
        if delta_pct > threshold:
            regressions.append(entry)
        elif delta_pct < -threshold:
            improvements.append(entry)
    return {
        "ok": not regressions,
        "threshold": threshold,
        "compared": compared,
        "regressions": regressions,
        "improvements": improvements,
    }
