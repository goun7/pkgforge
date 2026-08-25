"""Tur-28 — history_db ve native_deb_converter orta-bant temizligi."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import core.history_db as HD
from core.history_db import HistoryDB

# --- yardimcilar -------------------------------------------------------------

class PragmaPatlatan:
    """sqlite3.Connection sarmalayici; journal PRAGMA'sini patlatir."""

    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return self._real.__enter__ is not None and self._real.__exit__(*a)

    def execute(self, sql, *a, **k):
        if sql.lstrip().upper().startswith("PRAGMA JOURNAL"):
            raise sqlite3.OperationalError("wal yok")
        return self._real.execute(sql, *a, **k)


def test_pragma_failure_falls_back(monkeypatch, tmp_path):
    gercek_connect = sqlite3.connect

    def sahte(path, *a, **k):
        return PragmaPatlatan(gercek_connect(path, *a, **k))

    monkeypatch.setattr(sqlite3, "connect", sahte)
    db = HistoryDB(tmp_path / "h.db")          # 66-67
    try:
        assert db.get_history() == []
    finally:
        pass


def test_upgrade_adds_missing_columns(tmp_path):
    yol = tmp_path / "eski.db"
    baglan = sqlite3.connect(yol)
    baglan.execute(
        "CREATE TABLE conversions (id INTEGER PRIMARY KEY, package_name TEXT,"
        " version TEXT, status TEXT, created_at TEXT,"
        " http_etag TEXT DEFAULT '', http_last_modified TEXT DEFAULT '')")
    baglan.commit()
    baglan.close()
    db = HistoryDB(yol)                        # 105 + 107 ALTER
    try:
        kolonlar = [r["name"] for r in
                    db._get_connection().execute(
                        "PRAGMA table_info(conversions)").fetchall()]
        assert "source_url" in kolonlar and "backup_pkg" in kolonlar
    finally:
        pass


def test_init_db_failure_logged(tmp_path):
    hedef = tmp_path / "kendisi-dizin"
    hedef.mkdir()
    db = HistoryDB(hedef)                      # 113-114
    assert db.db_path == hedef


def _stat_patlatan(hedef):
    gercek = Path.stat

    def sahte(self, *a, **k):
        if self.name == hedef:
            raise OSError("stat yok")
        return gercek(self, *a, **k)

    return sahte


def test_usage_stats_arch_oserror(monkeypatch, tmp_path):
    db = HistoryDB(tmp_path / "h.db")
    cikti = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    cikti.write_bytes(b"x")
    monkeypatch.setattr(Path, "stat", _stat_patlatan(cikti.name))
    db.add_record(package_name="demo", original_file="/k.deb",
                  package_type="deb", sha256="ab", status="success",
                  output_pkg=str(cikti))
    istatistik = db.get_usage_stats()          # 176-177
    assert isinstance(istatistik, dict)


def test_usage_stats_db_error(monkeypatch, tmp_path):
    db = HistoryDB(tmp_path / "h.db")

    def patla(*a, **k):
        raise sqlite3.Error("kirik")
    monkeypatch.setattr(db, "_conn", patla)
    istatistik = db.get_usage_stats()          # 180-181
    assert istatistik.get("total", 0) == 0 or istatistik == {}


def test_add_record_db_error_returns_zero(monkeypatch, tmp_path):
    db = HistoryDB(tmp_path / "h.db")

    def patla(*a, **k):
        raise sqlite3.Error("kirik")
    monkeypatch.setattr(db, "_conn", patla)
    assert db.add_record(package_name="x", original_file="/s",
                         package_type="rpm", sha256="cd", status="success") == 0


def test_get_history_db_error(monkeypatch, tmp_path):
    db = HistoryDB(tmp_path / "h.db")

    def patla(*a, **k):
        raise sqlite3.Error("kirik")
    monkeypatch.setattr(db, "_conn", patla)
    assert db.get_history() == []              # 268-269


def test_search_db_error(monkeypatch, tmp_path):
    db = HistoryDB(tmp_path / "h.db")

    def patla(*a, **k):
        raise sqlite3.Error("kirik")
    monkeypatch.setattr(db, "_conn", patla)
    assert db.get_records_for_package("hiçbiri") == []   # 306-307


def test_clear_history_db_error(monkeypatch, tmp_path):
    db = HistoryDB(tmp_path / "h.db")

    def patla(*a, **k):
        raise sqlite3.Error("kirik")
    monkeypatch.setattr(db, "_conn", patla)
    db.clear_history()                          # 317-318


def test_update_http_headers_db_error(monkeypatch, tmp_path):
    db = HistoryDB(tmp_path / "h.db")

    def patla(*a, **k):
        raise sqlite3.Error("kirik")
    monkeypatch.setattr(db, "_conn", patla)
    db.update_http_headers(99, "e", "m")        # 329-330


def test_backup_package_paths(tmp_path, monkeypatch):
    db = HistoryDB(tmp_path / "h.db")
    # buyuk dosya -> stream_copy yolu (223-225)
    buyuk = tmp_path / "buyuk.pkg.tar.zst"
    with open(buyuk, "wb") as fh:
        fh.seek(11 * 1024 * 1024)
        fh.write(b"x")
    kopya = {}
    monkeypatch.setattr(HD, "backup_dir", lambda: tmp_path / "backups")
    (tmp_path / "backups").mkdir()
    import core.streaming as ST
    def sahte_kopya(a, b):
        Path(b).write_bytes(b"y")
        kopya["hedef"] = str(b)
        return b
    monkeypatch.setattr(ST, "stream_copy", sahte_kopya)
    sonuc = db.backup_package(buyuk)
    assert sonuc is not None and sonuc.exists()

    # OSError -> 230-232
    def patla(a, b):
        raise OSError("disk dolu")
    monkeypatch.setattr(ST, "stream_copy", patla)
    assert db.backup_package(buyuk) is None

def test_backup_missing_file_returns_none(tmp_path):
    db = HistoryDB(tmp_path / "h.db")
    assert db.backup_package(tmp_path / "yok.pkg.tar.zst") is None


def test_backup_small_file_uses_copy2(tmp_path, monkeypatch):
    db = HistoryDB(tmp_path / "h.db")
    kucuk = tmp_path / "kucuk.pkg.tar.zst"
    kucuk.write_bytes(b"abc")
    monkeypatch.setattr(HD, "backup_dir", lambda: tmp_path / "backups")
    (tmp_path / "backups").mkdir()
    hedef = db.backup_package(kucuk)
    assert hedef is not None and hedef.read_bytes() == b"abc"
