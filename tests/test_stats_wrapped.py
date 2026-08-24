"""Faz 5 (F5.24) — Stats Wrapped yillik donusum raporu."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from core.stats_wrapped import build_wrapped

_SCHEMA = (
    "CREATE TABLE conversions ("
    " id INTEGER PRIMARY KEY,"
    " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,"
    " package_name TEXT NOT NULL,"
    " original_file TEXT,"
    " package_type TEXT NOT NULL,"
    " sha256 TEXT,"
    " status TEXT NOT NULL,"
    " output_pkg TEXT,"
    " details TEXT,"
    " source_url TEXT)"
)


def _seed(db: Path, rows):
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.execute(_SCHEMA)
    conn.executemany(
        "INSERT INTO conversions (timestamp, package_name, package_type,"
        " status, source_url) VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()


def test_missing_db_returns_empty_report(tmp_path):
    r = build_wrapped(year=2026, db_path=tmp_path / "nope.db")
    assert r["total"] == 0
    assert r["year"] == 2026


def test_empty_table_returns_empty_report(tmp_path):
    db = tmp_path / "h.db"
    _seed(db, [])
    r = build_wrapped(year=2026, db_path=db)
    assert r["total"] == 0


def test_wrapped_aggregates_and_filters_by_year(tmp_path):
    db = tmp_path / "h.db"
    _seed(db, [
        ("2026-01-05 10:00:00", "foo", "deb", "success", ""),
        ("2026-01-20 10:00:00", "foo", "deb", "converted", "http://x"),
        ("2026-03-11 10:00:00", "bar", "rpm", "failed", ""),
        ("2026-03-15 10:00:00", "baz", "deb", "installed", ""),
        ("2025-06-01 10:00:00", "old", "deb", "success", ""),  # baska yil
    ])
    r = build_wrapped(year=2026, db_path=db)
    assert r["total"] == 4          # 2025 kaydi disarida
    assert r["success"] == 3        # success+converted+installed
    assert r["failed"] == 1
    assert r["success_rate"] == 75.0
    assert r["distinct_packages"] == 3
    assert r["url_count"] == 1
    assert r["busiest_month"] in ("Ocak", "Mart")  # her ikisi de 2 kayit
    top_names = [p["name"] for p in r["top_packages"]]
    assert top_names[0] == "foo"    # foo 2 kez
    assert r["by_type"]["deb"] == 3
    assert r["by_type"]["rpm"] == 1


def test_wrapped_month_labels_are_turkish(tmp_path):
    db = tmp_path / "h.db"
    _seed(db, [("2026-12-01 10:00:00", "a", "deb", "success", "")])
    r = build_wrapped(year=2026, db_path=db)
    assert "Aralik" in r["by_month"]
    assert r["busiest_month"] == "Aralik"


def test_rpc_stats_wrapped(tmp_path, monkeypatch):
    import core.api_server as A
    import core.stats_wrapped as SW

    db = tmp_path / "h.db"
    _seed(db, [("2026-02-01 10:00:00", "a", "deb", "success", "")])
    monkeypatch.setattr(SW, "history_db_path", lambda profile=None: db)
    out = A.handle_stats_wrapped({"year": 2026})
    assert out["total"] == 1
    assert out["year"] == 2026
