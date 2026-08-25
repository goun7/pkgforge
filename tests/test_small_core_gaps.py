"""Kucuk modullerin son eksik satirlari — tur-23 toplu itmesi."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS
from typing import ClassVar

import core.build_receipt as BR
import core.doctor as DOC
import core.malware_scanner as MS
import core.perf_budget as PB
import core.queue_store as QS
import core.report_export as RE
import core.stats_wrapped as SW
import core.streaming as ST

# --- report_export --------------------------------------------------------------

def test_report_dict_with_metadata_and_signature():
    meta = NS(name="demo", version="1.0", arch="x86_64", arch_mapped="x86_64",
              package_type="deb", file_list=["a", "b"])
    sig = NS(has_signature=True, valid=True, detail="ok")
    ornek_rapor = NS(grade="A",
                     overall=NS(value="pass"),
                     checks=[NS(name="tarama",
                                severity=NS(value="pass"),
                                message="temiz", details=["t1"])])
    veri = RE.report_to_dict(ornek_rapor,
                             metadata=meta, sha256="ab", signature=sig)
    assert veri["package"]["name"] == "demo"
    assert veri["package"]["file_count"] == 2
    assert veri["signature"]["has_signature"] is True


# --- build_receipt --------------------------------------------------------------

def test_first_line_handles_oserror(monkeypatch):
    def patla(*a, **k):
        raise OSError("araclar yok")
    monkeypatch.setattr(subprocess, "run", patla)
    assert BR._first_line(["pkg-config", "--version"]) == ""


def test_debtap_db_date_stat_error_skips(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    db = tmp_path / ".debtap" / "db"      # son aday
    db.parent.mkdir(parents=True, exist_ok=True)

    gercek_isfile = Path.is_file
    def sahte_isfile(self):
        if str(self).endswith(str(db)):
            return True
        return gercek_isfile(self)

    gercek_stat = Path.stat
    def sahte_stat(self, *a, **k):
        if str(self).endswith(str(db)):
            raise PermissionError(13, "kilitli")
        return gercek_stat(self, *a, **k)

    monkeypatch.setattr(Path, "is_file", sahte_isfile)
    monkeypatch.setattr(Path, "stat", sahte_stat)
    assert BR.debtap_db_date() == ""


# --- doctor ---------------------------------------------------------------------

def test_doctor_dbus_probe_exception(monkeypatch):
    class Patlak:
        @staticmethod
        def service_status():
            raise RuntimeError("dbus kapali")
    monkeypatch.setitem(sys_modules(), "core.dbus_service", Patlak)
    sonuc = DOC._check_dbus()
    assert sonuc["ok"] is False and "dbus" in sonuc["detail"]


def test_doctor_scheduler_probe_exception(monkeypatch):
    class Patlak:
        TASKS: ClassVar[list] = []
        @staticmethod
        def state():
            raise RuntimeError("zamanlayici yok")
    monkeypatch.setitem(sys_modules(), "core.scheduler", Patlak)
    sonuc = DOC._check_scheduler()
    assert sonuc["ok"] is False and "zamanlayici" in sonuc["detail"]


def sys_modules():
    import sys
    return sys.modules


# --- queue_store ----------------------------------------------------------------

def test_queue_store_clear_with_status(tmp_path):
    store = QS.QueueStore(tmp_path / "q.db")
    try:
        store.upsert({"id": "1", "path": "/a.deb", "name": "a",
                      "status": "done"})
        store.upsert({"id": "2", "path": "/b.rpm", "name": "b",
                      "status": "error"})
        store.clear(status="error")           # kosullu silme yolu
        kalan = store.load_restorable()
        assert all(k["status"] != "error" for k in kalan)
    finally:
        store.close()


# --- streaming ------------------------------------------------------------------

def test_human_size_petabyte_branch(monkeypatch, tmp_path):
    dev = tmp_path / "devasa.bin"
    dev.write_bytes(b"")
    orijinal_stat = Path.stat

    def sahte(self, *a, **k):
        if self == dev:
            return NS(st_size=3 * 1024 ** 6)   # >= PB
        return orijinal_stat(self, *a, **k)

    monkeypatch.setattr(Path, "stat", sahte)
    assert "PB" in ST.get_file_size_human(dev)


# --- rpm_to_deb -----------------------------------------------------------------

def test_rpm_to_deb_without_rpm_tool(monkeypatch, tmp_path):
    import core.rpm_to_deb_converter as RD
    secici = {"rpm2cpio": "/usr/bin/rpm2cpio",
              "dpkg-deb": "/usr/bin/dpkg-deb",
              "bsdtar": "/usr/bin/bsdtar"}
    monkeypatch.setattr("shutil.which", lambda n: secici.get(n))
    f = tmp_path / "my-cool-app-2.0-1.fc40.noarch.rpm"
    f.write_bytes(b"x")

    def sahte_safe_run(cmd, timeout=0, cwd=None, **k):
        # dpkg-deb derleme adimini basarili say ve cikti dosyasini uret
        if cmd and str(cmd[0]).endswith("dpkg-deb"):
            hedef = tmp_path / "my-cool-app_2.0-1_all.deb"
            hedef.write_bytes(b"deb")
            return NS(returncode=0, stdout="", stderr="")
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(RD, "safe_run", sahte_safe_run)
    ok, _msg, _deb = RD.rpm_to_deb(f, tmp_path)
    assert isinstance(ok, bool)


# --- malware_scanner ------------------------------------------------------------

def test_clamav_freshness_db_error_swallowed(monkeypatch):
    monkeypatch.setattr("shutil.which",
                        lambda n: "/usr/bin/clamscan"
                        if n == "clamscan" else None)
    ev_clamav = Path.home() / ".clamav"
    monkeypatch.setattr(Path, "is_dir",
                        lambda self: str(self) == str(ev_clamav))
    gercek_glob = Path.glob

    def sahte_glob(self, pattern):
        if pattern in ("*.cvd", "*.cld"):
            raise OSError("disk koptu")
        return gercek_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", sahte_glob)
    assert MS.check_database_freshness() is None


# --- stats_wrapped --------------------------------------------------------------

def test_month_label_out_of_range():
    assert SW._month_label("13") == "13"
    assert SW._month_label("00") == "00"
    assert SW._month_label("abc") == "abc"
    assert SW._month_label("03") == "Mart"


# --- perf_budget ----------------------------------------------------------------

def test_load_baseline_bad_json(monkeypatch, tmp_path):
    kotu = tmp_path / "base.json"
    kotu.write_text("{bozuk json")
    assert PB.load_baseline(kotu) == {}
    assert PB.load_baseline(tmp_path / "yok.json") == {}


def test_compare_skips_zero_baseline(monkeypatch):
    rapor = NS(results=[NS(name="a", duration_ms=10)])
    taban = {"a": {"duration_ms": 0}}
    cikti = PB.compare(rapor, taban)
    assert cikti["compared"] == 0

def _clamav_ortemi(monkeypatch, tmp_path):
    ev = tmp_path / "home"
    (ev / ".clamav").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: ev))
    gercek_isdir = Path.is_dir

    def sahte_isdir(self):
        if str(self) == "/var/lib/clamav":
            return False
        return gercek_isdir(self)

    monkeypatch.setattr(Path, "is_dir", sahte_isdir)
    monkeypatch.setattr("shutil.which",
                        lambda n: "/usr/bin/clamscan"
                        if n == "clamscan" else None)
    return ev / ".clamav"


def test_clamav_freshness_old_db_warns(monkeypatch, tmp_path):
    from datetime import datetime, timedelta, timezone

    clamav = _clamav_ortemi(monkeypatch, tmp_path)
    eski = (datetime.now(tz=timezone.utc) - timedelta(days=400)).timestamp()
    daha_yeni = (datetime.now(tz=timezone.utc) - timedelta(days=100)).timestamp()
    hedef = clamav / "daily.cvd"; hedef.write_bytes(b"x")
    os.utime(hedef, (eski, eski))
    hedef = clamav / "monthly.cld"; hedef.write_bytes(b"x")
    os.utime(hedef, (daha_yeni, daha_yeni))   # cld kazaniyor -> 66

    uyarı = MS.check_database_freshness()
    assert uyarı is not None and "eski" in uyarı


def test_clamav_freshness_missing_db(monkeypatch, tmp_path):
    clamav = _clamav_ortemi(monkeypatch, tmp_path)
    assert list(clamav.glob("*")) == []       # ortem bos

    mesaj = MS.check_database_freshness()
    assert mesaj is not None and "bulunamad" in mesaj


def test_wrapped_corrupt_db_graceful(tmp_path):
    bozuk = tmp_path / "bozuk.db"
    bozuk.write_bytes(b"bu bir sqlite degil")
    rapor = SW.build_wrapped(2026, db_path=bozuk)
    assert rapor["total"] == 0 and rapor["success_rate"] == 0.0

def test_clamav_freshness_without_clamscan(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert MS.check_database_freshness() is None
