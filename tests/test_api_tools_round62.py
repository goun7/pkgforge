"""Tur-62 — Feature Tezgahi RPC handlerlari (tools.rpm_to_deb/abi_check/audit)."""
from __future__ import annotations

import pytest

import core.api_server as AS


@pytest.fixture()
def senkron(monkeypatch):
    """_run_thread'i senkrona cevir, olaylari kaydet."""
    kayit = []

    def sahte(fn, event_name="event/security_done"):
        try:
            sonuc = fn()
            kayit.append((event_name, {"ok": True, "sonuc": sonuc}))
        except Exception as exc:  # noqa: BLE001
            kayit.append((event_name, {"ok": False, "hata": str(exc)}))

    monkeypatch.setattr(AS, "_run_thread", sahte)
    return kayit


def _rec(**kw):
    from core.history_db import HistoryRecord
    base = {"id": 1, "timestamp": "2026-08-27", "package_name": "p",
            "original_file": "p.deb", "package_type": "deb", "sha256": "a",
            "status": "installed", "output_pkg": "", "details": "",
            "source_url": "", "backup_pkg": "", "http_etag": "",
            "http_last_modified": ""}
    base.update(kw)
    return HistoryRecord(**base)


# ── tools.rpm_to_deb ────────────────────────────────────────────
def test_rpm_to_deb_success(senkron, tmp_path, monkeypatch):
    rpm = tmp_path / "p.rpm"
    rpm.write_bytes(b"x")
    import core.rpm_to_deb_converter as R2D
    monkeypatch.setattr(R2D, "is_rpm_to_deb_available", lambda: True)
    monkeypatch.setattr(R2D, "rpm_to_deb",
                        lambda p, o: (True, "donustu", tmp_path / "p.deb"))
    yanit = AS.handle_tools_rpm_to_deb({"rpm": str(rpm), "output_dir": str(tmp_path)})
    assert yanit == {"started": True}
    assert senkron[0][0] == "event/rpm_to_deb_done"
    sonuc = senkron[0][1]["sonuc"]
    assert sonuc["ok"] is True and sonuc["message"] == "donustu"
    assert sonuc["deb_path"].endswith("p.deb")


def test_rpm_to_deb_default_outdir(senkron, tmp_path, monkeypatch):
    rpm = tmp_path / "p.rpm"
    rpm.write_bytes(b"x")
    import core.rpm_to_deb_converter as R2D
    monkeypatch.setattr(R2D, "is_rpm_to_deb_available", lambda: True)
    monkeypatch.setattr(R2D, "rpm_to_deb", lambda p, o: (True, "ok", None))
    AS.handle_tools_rpm_to_deb({"rpm": str(rpm)})
    assert senkron[0][1]["sonuc"]["deb_path"] is None


def test_rpm_to_deb_missing_file(senkron, tmp_path):
    with pytest.raises(FileNotFoundError):
        AS.handle_tools_rpm_to_deb({"rpm": str(tmp_path / "yok.rpm")})


def test_rpm_to_deb_tool_missing(senkron, tmp_path, monkeypatch):
    rpm = tmp_path / "p.rpm"
    rpm.write_bytes(b"x")
    import core.rpm_to_deb_converter as R2D
    monkeypatch.setattr(R2D, "is_rpm_to_deb_available", lambda: False)
    AS.handle_tools_rpm_to_deb({"rpm": str(rpm)})
    sonuc = senkron[0][1]["sonuc"]
    assert sonuc["ok"] is False and "bulunamadi" in sonuc["message"]


# ── tools.abi_check ─────────────────────────────────────────────
def test_abi_check_success(senkron, tmp_path, monkeypatch):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    import core.abi_scanner as ABI
    report = ABI.ABIScanReport(binary_count=2, checked_symbols=10)
    monkeypatch.setattr(ABI, "check_abi_compatibility", lambda p: report)
    yanit = AS.handle_tools_abi_check({"package": str(pkg)})
    assert yanit == {"started": True}
    assert senkron[0][0] == "event/abi_check_done"
    sonuc = senkron[0][1]["sonuc"]
    assert sonuc["passed"] is True
    assert sonuc["binary_count"] == 2
    assert sonuc["error_count"] == 0
    assert "summary" in sonuc


def test_abi_check_missing_file(senkron, tmp_path):
    with pytest.raises(FileNotFoundError):
        AS.handle_tools_abi_check({"package": str(tmp_path / "yok.pkg.tar.zst")})


# ── tools.audit ─────────────────────────────────────────────────
def test_audit_success(monkeypatch):
    import core.history_db as HD
    recs = [_rec(status="installed", package_type="deb"),
            _rec(id=2, status="converted", package_type="rpm", package_name="q")]

    class FakeDB:
        def get_history(self, limit=100):
            return recs

    monkeypatch.setattr(HD, "HistoryDB", FakeDB)
    yanit = AS.handle_tools_audit({})
    assert yanit["total"] == 2
    assert yanit["status_counts"] == {"installed": 1, "converted": 1}
    assert yanit["type_counts"] == {"deb": 1, "rpm": 1}
    assert yanit["integrity_issues"] == 0
    assert yanit["anomalies"] == 0
    assert len(yanit["records"]) == 2


def test_audit_date_filter_and_limit(monkeypatch):
    import core.history_db as HD
    recs = [_rec(timestamp="2026-01-01"), _rec(id=2, timestamp="2026-08-27"),
            _rec(id=3, timestamp="2027-01-01")]
    captured = {}

    class FakeDB:
        def get_history(self, limit=100):
            captured["limit"] = limit
            return recs

    monkeypatch.setattr(HD, "HistoryDB", FakeDB)
    yanit = AS.handle_tools_audit({"date_from": "2026-06-01",
                                   "date_to": "2026-12-31", "limit": 7})
    assert captured["limit"] == 7
    assert yanit["total"] == 1
    assert yanit["records"][0]["timestamp"] == "2026-08-27"


def test_audit_integrity_issues(monkeypatch, tmp_path):
    import core.history_db as HD
    recs = [_rec(output_pkg=str(tmp_path / "silinmis.pkg.tar.zst")),
            _rec(id=2, backup_pkg=str(tmp_path / "yedek_yok.tar.gz"))]

    class FakeDB:
        def get_history(self, limit=100):
            return recs

    monkeypatch.setattr(HD, "HistoryDB", FakeDB)
    assert AS.handle_tools_audit({})["integrity_issues"] == 2


def test_audit_anomaly(monkeypatch):
    import core.history_db as HD
    recs = [_rec(id=i, package_name="tekrar") for i in range(4)]

    class FakeDB:
        def get_history(self, limit=100):
            return recs

    monkeypatch.setattr(HD, "HistoryDB", FakeDB)
    assert AS.handle_tools_audit({})["anomalies"] == 1


def test_tools_methods_registered():
    assert AS.METHODS["tools.rpm_to_deb"] is AS.handle_tools_rpm_to_deb
    assert AS.METHODS["tools.abi_check"] is AS.handle_tools_abi_check
    assert AS.METHODS["tools.audit"] is AS.handle_tools_audit
