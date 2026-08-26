"""Tur-51 batch-1 — package_signing, cli_bridge, capabilities, upstream_tracker."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import core.package_signing as PS
import core.upstream_tracker as UT

# ── package_signing 62-81 / 94 / 130-139 / 147 ────────────────────────────────────

def test_sign_package_full_flow(monkeypatch, tmp_path):
    pkg = tmp_path / "paket.pkg.tar.zst"
    pkg.write_bytes(b"P")

    # gpg yok (56-57 zaten var) — imza akisina gir (62+)
    monkeypatch.setattr(PS, "is_gpg_available", lambda: True)

    # paket yok dalı (59-60)
    ok, msg = PS.sign_package(tmp_path / "yok.pkg.tar.zst", "paket")
    assert ok is False and "bulunamad" in msg

    # anahtar + parola ile basarisiz gpg (64-75)
    anahtar = tmp_path / "anahtar.gpg"
    anahtar.write_bytes(b"K")
    monkeypatch.setattr(PS, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=2, stderr="gizli anahtar yok"))
    ok, msg = PS.sign_package(pkg, key_path=anahtar,
                              passphrase="parola")
    assert ok is False and "başarısız" in msg

    # rc=0 ama .sig uretilmedi (77-78)
    monkeypatch.setattr(PS, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=0, stderr=b""))
    ok, msg = PS.sign_package(pkg)
    assert ok is False and "oluşturulamadı" in msg

    # basari yoli (80-81): safe_run icinde sig dosyasi olustur
    def uret(cmd, timeout=0):
        Path(str(cmd[-1]) + ".sig").write_bytes(b"S")
        return NS(returncode=0, stderr=b"")
    monkeypatch.setattr(PS, "safe_run", uret)
    ok, msg = PS.sign_package(pkg)
    assert ok is True and "İmza oluşturuldu" in msg


def test_verify_signature_paths(monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")

    # gpg yok (93-94)
    monkeypatch.setattr(PS, "is_gpg_available", lambda: False)
    bilgi = PS.verify_signature(pkg)
    assert bilgi.signed is False and "gpg bulunamadı" in bilgi.detail

    monkeypatch.setattr(PS, "is_gpg_available", lambda: True)

    # sig dosyasi yok (97-98)
    bilgi = PS.verify_signature(pkg)
    assert "İmza dosyası bulunamadı" in bilgi.detail

    # tam GPG ciktisi: GOODSIG/VALIDSIG/TRUST_ULTIMATE/SIG_ID (113-132)
    sig = Path(str(pkg) + ".sig")
    sig.write_bytes(b"S")
    cikti = (
        "gpg: İmza kontrol edildi\n"
        "[GNUPG:] GOODSIG ABCD1234 Ayşe Yılmaz <ayse@ornek.org>\n"
        "[GNUPG:] VALIDSIG AAAA1111BBBB2222 2026-01-01 1735689600\n"
        "[GNUPG:] TRUST_ULTIMATE\n"
        "[GNUPG:] SIG_ID paket.sig 2026-01-01 1735689600\n"
    )
    monkeypatch.setattr(PS, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=0, stdout=cikti, stderr=""))
    bilgi = PS.verify_signature(pkg)
    assert bilgi.signed and bilgi.valid
    assert bilgi.key_id == "ABCD1234"
    assert bilgi.signer == "Ayşe Yılmaz <ayse@ornek.org>"
    assert bilgi.key_fingerprint == "AAAA1111BBBB2222"
    assert bilgi.timestamp == "1735689600"
    assert "geçerli" in bilgi.detail                                  # 134-135

    # imzali ama gecerli degil (136-137)
    cikti2 = "[GNUPG:] GOODSIG ABCD1234 Ayşe Yılmaz <a@b.c>\n"
    monkeypatch.setattr(PS, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=1, stdout=cikti2, stderr=""))
    bilgi2 = PS.verify_signature(pkg)
    assert bilgi2.signed and not bilgi2.valid
    assert "doğrulanamadı" in bilgi2.detail

    # hicbir tanima satiri yok (138-139)
    monkeypatch.setattr(PS, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=1,
                                                  stdout="", stderr=""))
    bilgi3 = PS.verify_signature(pkg)
    assert "Geçerli imza bulunamadı" in bilgi3.detail


def test_list_keys_unavailable(monkeypatch):
    monkeypatch.setattr(PS, "is_gpg_available", lambda: False)
    assert PS.list_keys() == []                                       # 146-147


# ── cli_bridge 53-54 / 87-95 / 101 / 103-112 ──────────────────────────────────────

class SahteSignal:
    def __init__(self):
        self._aboneler = []

    def connect(self, fn):
        self._aboneler.append(fn)

    def emit(self, *a):
        for fn in list(self._aboneler):
            fn(*a)


def _sahte_donusumcu(monkeypatch, modul_adi, sinif_adi, satirlar,
                     sonuc=(True, "tamam", "cikti.pkg")):
    class SahteDonusumcu:
        def __init__(self, tools, parent=None):
            self.output_line = SahteSignal()
            self.finished = SahteSignal()

        def convert(self, yol, dizin, meta=None):
            for s in satirlar:
                self.output_line.emit(s)
            pkg = Path(sonuc[2]) if isinstance(sonuc[2], str) else sonuc[2]
            self.finished.emit(sonuc[0], sonuc[1], pkg)

    import importlib
    modul = importlib.import_module(modul_adi)
    monkeypatch.setattr(modul, sinif_adi, SahteDonusumcu)


def test_convert_deb_sync_with_progress(monkeypatch, tmp_path):
    import core.cli_bridge as CB
    deb = tmp_path / "x.deb"
    deb.write_bytes(b"D")
    _sahte_donusumcu(monkeypatch, "core.subprocess_converters",
                     "NativeDebConverterSubprocess",
                     ["adim 1", "adim 2"], (True, "ok", str(tmp_path / "o.pkg")))
    gorunen = []
    sonuc = CB.convert_deb_sync(deb, tmp_path,
                                progress_callback=gorunen.append)
    assert gorunen == ["adim 1", "adim 2"]                            # 52-54
    assert sonuc.success is True and sonuc.message == "ok"
    assert isinstance(sonuc.output_pkg, Path)                         # 56-67


def test_convert_rpm_sync_meta_and_analyze_fail(monkeypatch, tmp_path):
    import core.cli_bridge as CB
    rpm = tmp_path / "x.rpm"
    rpm.write_bytes(b"R")

    # meta verilmis (100-101) + progress (87-95)
    _sahte_donusumcu(monkeypatch, "core.subprocess_converters",
                     "RpmConverterSubprocess",
                     ["rpm adim"], (True, "hazir", str(tmp_path / "r.pkg")))
    gorunen = []
    meta = NS(name="x")
    sonuc = CB.convert_rpm_sync(rpm, tmp_path, meta=meta,
                                progress_callback=gorunen.append)
    assert gorunen == ["rpm adim"]
    assert sonuc.success is True                                      # 91-95

    # meta None + analiz hatasi (103-108)
    pa = sys.modules.setdefault("core.package_analyzer", NS())
    def patlak(p, t):
        raise ValueError("bozuk rpm")
    monkeypatch.setattr(pa, "analyze_package", patlak, raising=False)
    sonuc2 = CB.convert_rpm_sync(rpm, tmp_path, tools=NS())
    assert sonuc2.success is False
    assert "RPM analizi başarısız" in sonuc2.message                  # 106-108

    # meta None + analiz basarili (109-110)
    monkeypatch.setattr(pa, "analyze_package",
                        lambda p, t: NS(name="x"), raising=False)
    _sahte_donusumcu(monkeypatch, "core.subprocess_converters",
                     "RpmConverterSubprocess", [],
                     (True, "tam", str(tmp_path / "r2.pkg")))
    sonuc3 = CB.convert_rpm_sync(rpm, tmp_path, tools=NS())
    assert sonuc3.success is True                                     # 109-110


# ── capabilities 97-99 / 114 / 117-118 / 121-129 ─────────────────────────────────

def test_capability_accessors_and_artifact(monkeypatch, tmp_path):
    import core.capabilities as CAP

    yol = CAP.privileged_helper_system_path()                         # 96-99
    assert isinstance(yol, str) and yol
    polkit_varsayilan = str(CAP.CAPABILITIES["polkit"]["helper_system_path"])
    assert CAP.action_exec_path("bilinmeyen") == polkit_varsayilan   # 102-108

    # artifact yok -> False (113-114)
    monkeypatch.setattr(CAP, "_ARTIFACT", tmp_path / "yok.json")
    assert CAP.artifact_matches() is False

    # bozuk json -> False (117-118)
    bozuk = tmp_path / "bozuk.json"
    bozuk.write_text("{kesik")
    monkeypatch.setattr(CAP, "_ARTIFACT", bozuk)
    assert CAP.artifact_matches() is False

    # eslesen artifact -> True (116)
    iyi = tmp_path / "iyi.json"
    iyi.write_text(json.dumps(CAP.CAPABILITIES, indent=2))
    monkeypatch.setattr(CAP, "_ARTIFACT", iyi)
    assert CAP.artifact_matches() is True


def test_capabilities_cli_emit_and_usage(tmp_path):
    hedef = tmp_path / "cap.json"

    r1 = subprocess.run(
        [sys.executable, "-m", "core.capabilities", "--emit", str(hedef)],
        check=False, capture_output=True, text=True,
        timeout=30,
        cwd=str(Path(__file__).resolve().parent.parent))
    assert r1.returncode == 0 and "yazildi" in r1.stdout              # 123-127
    assert json.loads(hedef.read_text(encoding="utf-8"))

    r2 = subprocess.run([sys.executable, "-m", "core.capabilities"],
                        check=False, capture_output=True, text=True,
        timeout=30,
                        cwd=str(Path(__file__).resolve().parent.parent))
    assert "kullanim" in r2.stdout                                    # 128-129


# ── upstream_tracker 137-151 ──────────────────────────────────────────────────────

def test_check_all_installed_updates(monkeypatch, tmp_path):
    import core.upstream_tracker as UT

    kayitlar = [
        NS(package_name="a", source_url="https://x/a",
           record_id=1, etag="", last_modified="", content_length=""),
        NS(package_name="a", source_url="https://x/a",
           record_id=2, etag="", last_modified="", content_length=""),
        NS(package_name="b", source_url="", record_id=3, etag="",
           last_modified="", content_length=""),
        NS(package_name="c", source_url="https://x/c",
           record_id=4, etag="", last_modified="", content_length=""),
    ]

    class SahteDB:
        def get_history(self, limit=50):
            return kayitlar
        def update_http_headers(self, rid, etag, lm):
            guncellenen.append((rid, etag, lm))

    guncellenen = []
    monkeypatch.setattr(UT, "HistoryDB", SahteDB)

    def sahte_kontrol(rec, offline=False):
        return UT.UpdateCheckResult(
            package_name=rec.package_name, source_url=rec.source_url,
            has_update=True, status="checked", etag="E1",
            last_modified="L1", record_id=rec.record_id)

    monkeypatch.setattr(UT, "check_upstream_update", sahte_kontrol)
    sonuclar = UT.check_all_installed_updates()                       # 137-151

    # a bir kez, b atlanir (url yok), c bir kez
    assert [r.package_name for r in sonuclar] == ["a", "c"]
    assert guncellenen == [(1, "E1", "L1"), (4, "E1", "L1")]          # 148-149

# ── upstream_tracker 44-126: check_upstream_update govdesi ────────────────────────

def _kayit(**ust):
    temel = {"package_name": "p", "source_url": "https://u/p",
             "has_update": False, "status": "", "etag": "",
             "last_modified": "", "content_length": "", "detail": "",
             "record_id": 7, "id": 7,
             "http_etag": "", "http_last_modified": ""}
    temel.update(ust)
    return NS(**temel)


def test_check_upstream_offline_and_no_url():
    r = UT.check_upstream_update(_kayit(), offline=True)              # 44-51
    assert r.status == "offline" and not r.has_update

    r2 = UT.check_upstream_update(_kayit(source_url="ftp://x"))       # 53-60
    assert r2.status == "no_url"

    r3 = UT.check_upstream_update(_kayit(source_url=""))
    assert r3.status == "no_url"


def test_check_upstream_head_paths(monkeypatch):
    import urllib.error

    class SahteYanit:
        def __init__(self, basliklar):
            self.headers = basliklar
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    # degisiklik var (ETag farki) — 100-102
    yanitlar = iter([
        SahteYanit({"ETag": '"YENI-ETAG"', "Last-Modified": "D1",
                    "Content-Length": "42"}),
        SahteYanit({"ETag": '"A"', "Last-Modified": "YENI-D"}),
        SahteYanit({"ETag": '"ILK"', "Last-Modified": ""}),
        SahteYanit({"ETag": '"AYNI"', "Last-Modified": "D1"}),
        SahteYanit({"ETag": '"X"', "Last-Modified": "DX"}),
    ])
    def sahte_urlopen(req, timeout=0):
        return next(yanitlar)
    monkeypatch.setattr(UT.urllib.request, "urlopen", sahte_urlopen)
    kayit = _kayit(http_etag="ESKI-ETAG", http_last_modified="D1")
    r = UT.check_upstream_update(kayit)
    assert r.status == "checked" and r.has_update is True
    assert "ETag değişti" in r.detail
    assert r.etag == "YENI-ETAG" and r.content_length == "42"
    assert r.record_id == 7

    # Last-Modified farki (103-105)
    kayit2 = _kayit(http_etag="A", http_last_modified="ESKI-D")
    r2 = UT.check_upstream_update(kayit2)
    assert r2.has_update and "Last-Modified değişti" in r2.detail     # 104-105

    # ilk kontrol (106-108)
    kayit3 = _kayit()
    r3 = UT.check_upstream_update(kayit3)
    assert not r3.has_update and "İlk kontrol" in r3.detail           # 107-108

    # degisiklik yok (109-110)
    kayit4 = _kayit(http_etag="AYNI", http_last_modified="D1")
    r4 = UT.check_upstream_update(kayit4)
    assert not r4.has_update and "tespit edilmedi" in r4.detail       # 109-110

    # URLError yolu (124-126+)
    def hata(req, timeout=0):
        raise urllib.error.URLError("sunucu erisilemiyor")
    monkeypatch.setattr(UT.urllib.request, "urlopen", hata)
    kayit5 = _kayit(http_etag="X")
    r5 = UT.check_upstream_update(kayit5)
    assert r5.status != "checked" and not r5.has_update


def test_is_gpg_available_true(monkeypatch):
    import shutil as shutil_mod
    monkeypatch.setattr(shutil_mod, "which", lambda n: "/usr/bin/gpg")
    assert PS.is_gpg_available() is True                              # 38


def test_sign_package_gpg_missing(monkeypatch, tmp_path):
    pkg = tmp_path / "a.pkg.tar.zst"
    pkg.write_bytes(b"P")
    monkeypatch.setattr(PS, "is_gpg_available", lambda: False)
    ok, msg = PS.sign_package(pkg)                                    # 56-57
    assert ok is False and "gpg bulunamadı" in msg


def test_list_keys_body(monkeypatch, tmp_path):
    """149-173: list_keys gpg-cikti ayristirma."""
    monkeypatch.setattr(PS, "is_gpg_available", lambda: True)

    satirlar = [
        "pub:-:4096:1:ABCD1234:1735689600::::::esc:",
        "fpr:::::::::AAAA1111BBBB2222:",
        ":".join(["uid"] + [""] * 8 + ["Ayşe Yılmaz <ayse@ornek.org>"]),
    ]
    cikti = "\n".join(satirlar)
    monkeypatch.setattr(PS, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=0,
                                                  stdout=cikti, stderr=""))
    anahtarlar = PS.list_keys()
    assert isinstance(anahtarlar, list) and len(anahtarlar) >= 1
    ilk = anahtarlar[0]
    assert any("ABCD1234" in str(v) for v in ilk.values())

    # bos cikti -> bos liste
    monkeypatch.setattr(PS, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=0,
                                                  stdout="", stderr=""))
    assert PS.list_keys() == []


# ── capabilities kalan erisimciler + main blogu (runpy) ─────────────────────

def test_capability_remaining_accessors():
    import core.capabilities as CAP
    assert isinstance(CAP.http_reader_methods(), frozenset)           # 76-80
    eylemler = CAP.polkit_actions()                                   # 83-87
    assert isinstance(eylemler, list)
    for oge in eylemler:
        assert len(oge) == 3
    assert CAP.helper_system_path()                                   # 90-93


def test_capabilities_main_block_runpy(monkeypatch, tmp_path, capsys):
    """122-129: modul main-blogu runpy ile ayni surecte kosulur."""
    import runpy

    hedef = tmp_path / "cap2.json"

    monkeypatch.setattr(sys, "argv",
                        ["core.capabilities", "--emit", str(hedef)])
    runpy.run_module("core.capabilities", run_name="__main__")
    assert json.loads(hedef.read_text(encoding="utf-8"))              # 123-127

    monkeypatch.setattr(sys, "argv", ["core.capabilities"])
    runpy.run_module("core.capabilities", run_name="__main__")
    yakalanan = capsys.readouterr()
    assert "kullanim" in yakalanan.out                                # 128-129