"""Maintainer-script sadakat testi — donusumde dusurulen preinst/postinst/prerm/postrm.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — `safe_run` MONKEYPATCH (gerçek ar/bsdtar/rpm YOK),
         control.tar liste çıktısı metin olarak üretilir, dosya sistemi tmp_path.

Neden var: Arch'un postinst/postrm kavramı yok; eşdeğeri .INSTALL hook'u.
Borrowed bir .deb'in bakım betikleri donusumde SESSIZCE kayboluyordu ve rapor
"A (pass)" diyordu — "kuruldu ama çalışmıyor" sınıfının kökü. Artık tespit
edilip WARNING olarak yuzeye cikiyor; yani not dürüstçe düsüyor.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core.compatibility_checker import (
    CheckSeverity,
    _check_maintainer_scripts,
    describe_script_hook,
    run_compatibility_checks,
)
from core.package_analyzer import (
    PackageMetadata,
    _extract_deb_maintainer_scripts,
)


def _cp(stdout: str = "", rc: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["x"], returncode=rc, stdout=stdout, stderr="")


# == _extract_deb_maintainer_scripts ==============================================================

def test_postinst_ve_postrm_tespit(monkeypatch):
    gorulen: list[dict] = []

    def sahte_run(cmd, *a, **k):
        gorulen.append({"cmd": cmd, "input": k.get("input")})
        return _cp(stdout="./control\n./postinst\n./postrm\n./md5sums\n")

    monkeypatch.setattr("core.package_analyzer.safe_run", sahte_run)
    meta = PackageMetadata()
    _extract_deb_maintainer_scripts("control.tar.xz", b"TARBYTES", meta, _tools())
    assert meta.maintainer_scripts == ["postinst", "postrm"]
    # control.tar baytlari YENIDEN okunmaz; cagiranin okudugu girdi kullanilir
    assert gorulen[0]["input"] == b"TARBYTES"


def test_kanonik_sira(monkeypatch):
    """Cikti sirasi girdi sirasindan bagimsiz, sabit enum sirasinda olur."""
    monkeypatch.setattr(
        "core.package_analyzer.safe_run",
        lambda cmd, *a, **k: _cp(stdout="postrm\npreinst\npostinst\nprerm\ncontrol\n"),
    )
    meta = PackageMetadata()
    _extract_deb_maintainer_scripts("control.tar.gz", b"", meta, _tools())
    assert meta.maintainer_scripts == ["preinst", "postinst", "prerm", "postrm"]


def test_betiysiz_paket_bos_liste(monkeypatch):
    monkeypatch.setattr(
        "core.package_analyzer.safe_run",
        lambda cmd, *a, **k: _cp(stdout="./control\n./md5sums\n"),
    )
    meta = PackageMetadata()
    _extract_deb_maintainer_scripts("control.tar", b"", meta, _tools())
    assert meta.maintainer_scripts == []


def test_listeleme_basarisizsa_sessiz_bos(monkeypatch):
    """ORTAM-OGRENDI: bsdtar rc!=0 -> alan HIC yazilmaz, analiz patlamaz."""
    monkeypatch.setattr(
        "core.package_analyzer.safe_run", lambda cmd, *a, **k: _cp(rc=2)
    )
    meta = PackageMetadata(maintainer_scripts=["SENTINEL"])
    _extract_deb_maintainer_scripts("control.tar.xz", b"", meta, _tools())
    assert meta.maintainer_scripts == ["SENTINEL"]


def test_bsdtar_yoksa_tar_yedegi_kullanimi(monkeypatch):
    """bsdtar bos ise `tar -t<f>` dallarina duser (arac yoksunlugu crash degil)."""
    gorulen: list[list[str]] = []

    def sahte_run(cmd, *a, **k):
        gorulen.append(cmd)
        return _cp(stdout="postinst\n")

    monkeypatch.setattr("core.package_analyzer.safe_run", sahte_run)
    meta = PackageMetadata()
    _extract_deb_maintainer_scripts("control.tar.gz", b"", meta, _tools(bsdtar=""))
    assert meta.maintainer_scripts == ["postinst"]
    assert gorulen[0][0] == "tar"
    assert gorulen[0][1] == "-tzf"  # .gz -> z bayragi


def test_guncel_analiz_control_tar_i_bir_kez_okur(monkeypatch):
    """Regresyon kilidi: betik tespiti ikinci bir 'ar p control.tar' dogurmaz."""
    okuma = {"n": 0}

    def sahte_run(cmd, *a, **k):
        if len(cmd) > 1 and cmd[1] == "t":          # ar t <deb> -> uye listesi
            return _cp(stdout="debian-binary\ncontrol.tar.xz\ndata.tar.xz\n")
        if len(cmd) > 1 and cmd[1] == "p":          # ar p <deb> <uye>
            if str(cmd[3]).startswith("control.tar"):
                okuma["n"] += 1
                return _cp(stdout=b"CONTROLBLOB")
            return _cp(stdout=b"DATABLOB")
        return _cp(stdout="Package: demo\nVersion: 1\n")

    monkeypatch.setattr("core.package_analyzer.safe_run", sahte_run)
    from core.package_analyzer import _analyze_deb

    _analyze_deb(Path("/x.deb"), _tools())
    assert okuma["n"] == 1, f"control.tar {okuma['n']} kez okundu (1 olmali)"


# == describe_script_hook =========================================================================

@pytest.mark.parametrize("name,hook", [
    ("preinst", "pre_install / pre_upgrade"),
    ("postinst", "post_install / post_upgrade"),
    ("prerm", "pre_remove"),
    ("postrm", "post_remove"),
])
def test_hook_eslemeleri(name, hook):
    assert describe_script_hook(name) == hook


def test_bilinmeyen_betik_soru_isareti():
    assert describe_script_hook("config") == "?"


# == _check_maintainer_scripts ====================================================================

def test_check_temiz_pas():
    r = _check_maintainer_scripts([])
    assert r.severity is CheckSeverity.PASS
    assert r.details == []


def test_check_betik_varsa_warning():
    r = _check_maintainer_scripts(["postinst", "postrm"])
    assert r.severity is CheckSeverity.WARNING
    assert len(r.details) == 2
    assert "post_install" in r.details[0]


def test_check_message_sayiyi_ve_isimleri_icerir():
    r = _check_maintainer_scripts(["preinst", "postinst", "prerm", "postrm"])
    assert "4" in r.message
    for s in ("preinst", "postinst", "prerm", "postrm"):
        assert s in r.message


# == run_compatibility_checks entegrasyonu ======================================================

def _tools(bsdtar: str = "/usr/bin/bsdtar"):
    from config import ToolPaths
    return ToolPaths(ar="/usr/bin/ar", bsdtar=bsdtar, pacman="", namcap="", ldd="")


def _safesiz(monkeypatch):
    """Tum dis komutlari (namcap/pacman/ldd) rc=1 ile patlat -> check'ler lokal kalsin."""
    monkeypatch.setattr(
        "core.compatibility_checker.safe_run",
        lambda cmd, *a, **k: _cp(rc=1),
    )


def test_rapor_betikleri_warning_olarak_tasir(monkeypatch, tmp_path):
    _safesiz(monkeypatch)
    pkg = tmp_path / "p-1.0-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"x")
    rep = run_compatibility_checks(pkg, [], [], _tools(), ["postinst"])
    matched = [c for c in rep.checks if c.severity is CheckSeverity.WARNING
               and "postinst" in c.message]
    assert matched, "dusurulen betik raporda gorunmuyor"


def test_not_betik_varsa_daha_kotu(monkeypatch, tmp_path):
    """ORTAM-OGRENDI: sessiz-A regresyonu — dusurulen betik notu kotulestirir.

    grade() yalnizca toplanan check'lerden turetilir (A = 0 warning), o yuzden
    iddia goreli kurulur: ayni paket + 1 betik = tam olarak 1 warning fazla.
    """
    _safesiz(monkeypatch)
    pkg = tmp_path / "p-1.0-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"x")
    with_scripts = run_compatibility_checks(pkg, [], [], _tools(), ["postinst"])
    without = run_compatibility_checks(pkg, [], [], _tools(), [])
    assert len(with_scripts.warnings) == len(without.warnings) + 1
    assert with_scripts.grade >= without.grade  # harf buyumesi = daha kotu
    assert not any("postinst" in c.message for c in without.warnings)


def test_parametre_varsayilani_none_geriye_udumlu(monkeypatch, tmp_path):
    """Geriye donuk uyum: 4 argumanla cagiran mevcut cagrilar kirilmaz."""
    _safesiz(monkeypatch)
    pkg = tmp_path / "p-1.0-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"x")
    rep = run_compatibility_checks(pkg, [], [], _tools())
    assert not any("postinst" in c.message for c in rep.warnings)
    # betik check'i PASS olarak rapora girmeye devam eder
    assert any(c.severity is CheckSeverity.PASS for c in rep.checks)


def test_metadata_alani_varsayilan_bos():
    assert PackageMetadata().maintainer_scripts == []
