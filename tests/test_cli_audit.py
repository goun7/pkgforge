"""Coverage itmesi - cli audit komutu (tarih filtresi, butunluk, anomaliler)."""
from __future__ import annotations

from types import SimpleNamespace as NS

import cli


def _rec(idx, status="installed", name="demo", ptype="deb", ts="2025-01-01",
         out="", backup="", url=""):
    return NS(id=idx, timestamp=ts, package_name=name, package_type=ptype,
              status=status, original_file=f"{name}.deb", output_pkg=out,
              backup_pkg=backup, source_url=url, http_etag="",
              http_last_modified="")


class FakeDB:
    def __init__(self, records):
        self._records = records

    def get_history(self, limit=100):
        return self._records[:limit]

    def get_records_for_package(self, n):
        return []

    def get_usage_stats(self):
        return {}


def test_audit_empty(capsys, monkeypatch):
    monkeypatch.setattr(cli, "HistoryDB", lambda: FakeDB([]))
    rc = cli._cmd_audit(NS(date_from=None, date_to=None))
    assert rc == 0 and "bulunamadı" in capsys.readouterr().out


def test_audit_full_trail(capsys, monkeypatch, tmp_path):
    good = tmp_path / "cikti.pkg.tar.zst"
    good.write_bytes(b"P")
    recs = [
        _rec(1, status="installed", out=str(good)),
        _rec(2, status="converted", name="iki", ptype="rpm"),
        _rec(3, status="oci_built", name="uc"),
    ]
    monkeypatch.setattr(cli, "HistoryDB", lambda: FakeDB(recs))
    rc = cli._cmd_audit(NS(date_from=None, date_to=None))
    out = capsys.readouterr().out
    assert rc == 0 and "Bütünlük" in out and "mevcut" in out
    assert "Anomali tespit edilmedi" in out
    assert "Detaylı Kayıtlar" in out and "iki" in out


def test_audit_integrity_and_anomalies(capsys, monkeypatch, tmp_path):
    recs = [
        _rec(1, status="installed", name="silinmis", out="/yok/cikti.deb"),
        _rec(2, status="install_failed", name="kirik", out=""),
        _rec(3, status="installed", name="baska", out=""),
    ] + [_rec(10 + i, status="converted", name="fazla") for i in range(4)]
    monkeypatch.setattr(cli, "HistoryDB", lambda: FakeDB(recs))
    rc = cli._cmd_audit(NS(date_from=None, date_to=None))
    out = capsys.readouterr().out
    assert rc == 0 and "silinmiş" in out and "bütünlük sorunu" in out
    assert "tekrarlayan süreç" in out
    assert "sorun kalıcı" in out


def test_audit_date_filter(capsys, monkeypatch):
    recs = [_rec(1, ts="2025-01-01"), _rec(2, ts="2025-06-01")]
    monkeypatch.setattr(cli, "HistoryDB", lambda: FakeDB(recs))
    rc = cli._cmd_audit(NS(date_from="2025-03-01", date_to=None))
    out = capsys.readouterr().out
    assert rc == 0 and "Toplam kayıt: 1" in out and "2025-06-01" in out