"""Faz 5 (F5.24) — Stats Wrapped: yillik donusum raporu.

Spotify-Wrapped tarzi, belirli bir yila ait donusum gecmisinden ozet uretir.
History db yoksa ya da bossa zarif duser (bos rapor doner, asla raise etmez).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from config import history_db_path

_MONTHS_TR = ["Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran",
              "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]

# Basari sayilan durumlar (pipeline "success"/"failed", sistem "installed"/
# "converted" yazar; hepsini kapsar).
_SUCCESS_STATUSES = {"success", "converted", "installed"}


def _month_label(mm: str) -> str:
    if mm.isdigit() and 1 <= int(mm) <= 12:
        return _MONTHS_TR[int(mm) - 1]
    return mm


def build_wrapped(year: int | None = None,
                  db_path: Any = None) -> dict[str, Any]:
    """Build the annual report for *year* (defaults to the current year)."""
    year = year or datetime.now(timezone.utc).year
    path = db_path or history_db_path()
    report: dict[str, Any] = {
        "year": year,
        "total": 0,
        "success": 0,
        "failed": 0,
        "success_rate": 0.0,
        "by_type": {},
        "by_month": {},
        "top_packages": [],
        "distinct_packages": 0,
        "busiest_month": "",
        "url_count": 0,
    }
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return report
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT package_name, package_type, status, source_url,"
            " strftime('%m', timestamp) AS m FROM conversions"
            " WHERE strftime('%Y', timestamp) = ?", (str(year),)).fetchall()
    except sqlite3.Error:
        return report
    finally:
        conn.close()

    if not rows:
        return report

    pkg_counts: dict[str, int] = {}
    by_month: dict[str, int] = {}
    by_type: dict[str, int] = {}
    success = 0
    url_count = 0
    for row in rows:
        name = row["package_name"]
        pkg_counts[name] = pkg_counts.get(name, 0) + 1
        pt = row["package_type"]
        by_type[pt] = by_type.get(pt, 0) + 1
        mm = row["m"] or ""
        if mm:
            by_month[mm] = by_month.get(mm, 0) + 1
        if row["status"] in _SUCCESS_STATUSES:
            success += 1
        if row["source_url"]:
            url_count += 1

    total = len(rows)
    busiest = max(by_month.items(), key=lambda kv: kv[1])[0] if by_month else ""
    top = sorted(pkg_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    report.update({
        "total": total,
        "success": success,
        "failed": total - success,
        "success_rate": round(100.0 * success / total, 1) if total else 0.0,
        "by_type": by_type,
        "by_month": {_month_label(k): v for k, v in sorted(by_month.items())},
        "top_packages": [{"name": n, "count": c} for n, c in top],
        "distinct_packages": len(pkg_counts),
        "busiest_month": _month_label(busiest),
        "url_count": url_count,
    })
    return report
