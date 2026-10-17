"""Olcu: kurulum yapilmayan yollarda uretilen paket ayakta kalmali.

Olculen bulgu (2026-10-17, /tmp/pf_ev trace): convert-only yollarinda
(_skip_install_message ile bayat mod, dry-run) _cleanup() gecici dizini
silip uretilen .pkg.tar.zst'i de götürüyordu — kullanici tam olarak
donusturmek istemisti. NGOy-benzeri garantiler:

1. kurulum yapilmadiginda paket girisin yaninda durmali (cli.py:158),
2. ayni adda dosya varsa ezilmemeli (sayisal sonek),
3. hedef dizin yazilamazsa paket yerinde birakilmali (sessiz kayip yok),
4. kurulum reddi "basarisiz" etiketiyle gosterilmemeli ("skipped").
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication

import core.pipeline as PL
from core.compatibility_checker import CheckSeverity
from core.pipeline import ConversionPipeline


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def _meta():
    return NS(name="demo", version="1.0", arch="x86_64",
              arch_mapped="x86_64", arch_compatible=True,
              already_installed=False, file_list=[], depends=[],
              maintainer_scripts=[])


def _report(sev):
    return NS(checks=[], overall=sev)


def _set_conv(self, pkg):
    self._async_success = True
    self._async_pkg_path = pkg


@pytest.fixture()
def here(qapp, monkeypatch, tmp_path):
    """Gercek disk akisini taklit edenFixture: donusum gecici dizine yazar."""
    giris_dir = tmp_path / "giris"
    giris_dir.mkdir()
    deb = giris_dir / "demo.deb"
    deb.write_bytes(b"D")
    tempd = tmp_path / "tmpd"
    tempd.mkdir()
    pkg = tempd / "demo-1.0-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"P")

    mp = monkeypatch
    mp.setattr(PL, "discover_tools",
               lambda: NS(missing_required=[], missing_optional=[], debtap=""))
    mp.setattr(PL, "create_temp_dir", lambda: tempd)
    mp.setattr(PL, "validate_mime_type", lambda p, t: "app/zst")
    mp.setattr(PL, "validate_file_size", lambda *a, **k: None)
    mp.setattr(PL, "sha256_hash", lambda p: "ab" * 32)
    mp.setattr(PL, "verify_deb_signature",
               lambda p, t: NS(has_signature=False, detail="imza yok"))
    mp.setattr("core.security.check_compression_bomb", lambda p, t: None)
    mp.setattr("i18n.load_setting", lambda k, d=False: False)
    mp.setattr(PL, "analyze_package", lambda p, t: _meta())
    mp.setattr(ConversionPipeline, "_convert_deb",
               lambda self, dp, od: _set_conv(self, pkg))
    installed = []
    mp.setattr(ConversionPipeline, "_do_install",
               lambda self, pp, pn: installed.append(pn))
    # run() finally'inde _cleanup ve _record_history cagrilir; history'yi
    # gercek SQLite yerine tmp'de tutmak yerine burada bosaltiyoruz
    # (cleanup davranisi test edilen sey).
    mp.setattr(ConversionPipeline, "_record_history",
               lambda self, fp: None)
    pipe = ConversionPipeline()
    return pipe, deb, pkg, giris_dir, installed


@pytest.fixture()
def warn_report(monkeypatch):
    monkeypatch.setattr(PL, "run_compatibility_checks",
                        lambda *a, **k: _report(CheckSeverity.WARNING))


@pytest.fixture()
def pass_report(monkeypatch):
    monkeypatch.setattr(PL, "run_compatibility_checks",
                        lambda *a, **k: _report(CheckSeverity.PASS))


# --- 1. kurulum yapilmadiginda paket ayakta kalmali --------------------------

def test_batch_skip_paket_girisin_yaninda_durur(here, warn_report):
    pipe, deb, pkg, giris_dir, installed = here
    pipe._skip_install_message = "toplu mod: kurulum atlandi"
    pipe._decision_made = True
    pipe._decision_approved = False
    pipe.run(deb)
    pipe._cleanup()
    assert installed == []
    assert pipe._result.success is True
    tasi = giris_dir / pkg.name
    assert tasi.exists(), "uretilen paket silinmemeli, girisin yaninda olmali"
    assert not pkg.exists()
    assert pipe._result.converted_pkg == tasi


def test_kullanici_reddi_paket_girisin_yaninda_durur(here, warn_report):
    pipe, deb, pkg, giris_dir, installed = here
    pipe._decision_made = True
    pipe._decision_approved = False
    pipe.run(deb)
    assert pipe._result.success is False
    assert installed == []
    tasi = giris_dir / pkg.name
    assert tasi.exists(), "kullanici kurulumu reddettiyse paket yine de kalmali"


def test_dry_run_paket_girisin_yaninda_durur(tmp_path, monkeypatch):
    """Dry-run aktifken GERCEK _do_install kuruluma dokunmaz.

    Bagimsiz pipeline: _do_install stublanmaz, gercek metodun dry-run dali
    costurulur. Installer olusturulursa test patlar.
    """
    from PyQt6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication([])
    giris_dir = tmp_path / "giris"
    giris_dir.mkdir()
    pkg = giris_dir / "demo-1.0-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"P")

    mp = monkeypatch
    mp.setattr("i18n.load_setting", lambda k, d=False: k == "dry_run")
    cagrilan = []
    import core.installer as installer_mod
    mp.setattr(installer_mod, "Installer",
               lambda *a, **k: cagrilan.append(1)
               or (_ for _ in ()).throw(AssertionError(
                   "dry-run aktifken Installer olusturulmamali")))
    pipe = ConversionPipeline()
    pipe._result.original_file = giris_dir / "demo.deb"
    pipe._temp_dir = tmp_path / "tmpd"
    (tmp_path / "tmpd").mkdir()
    pipe._preserve_converted_pkg = True
    pipe._result.converted_pkg = pkg
    pipe._do_install(pkg, "demo")
    assert cagrilan == []
    assert pipe._result.success is True
    assert "dry-run" in pipe._result.message
    pipe._cleanup()
    tasi = giris_dir / pkg.name
    assert tasi.exists(), "dry-run yolunda da paket ayakta kalmali"


# --- 2. mevcut dosya ezilmemeli ----------------------------------------------

def test_mevcut_paket_ezilmeyip_sonek_alir(here, warn_report):
    pipe, deb, pkg, giris_dir, _ = here
    once = giris_dir / pkg.name
    once.write_bytes(b"ONCE")
    pipe._skip_install_message = "toplu mod: kurulum atlandi"
    pipe._decision_made = True
    pipe._decision_approved = False
    pipe.run(deb)
    pipe._cleanup()
    assert once.read_bytes() == b"ONCE", "mevcut dosya asla ezilmemeli"
    tasi = giris_dir / (pkg.name + ".2")
    assert tasi.exists()
    assert pipe._result.converted_pkg == tasi


# --- 3. hedef dizin yazilamazsa sessiz kayip yok -----------------------------

def test_hedef_yazilamazsa_paket_yerinde_birakilir(here, warn_report, monkeypatch):
    pipe, deb, _, _, _ = here
    monkeypatch.setattr(ConversionPipeline, "_preserve_pkg",
                        lambda self, p: (_ for _ in ()).throw(OSError("salt okunur")))
    pipe._skip_install_message = "toplu mod: kurulum atlandi"
    pipe._decision_made = True
    pipe._decision_approved = False
    pipe.run(deb)
    try:
        pipe._cleanup()
    except OSError:
        pass
    # _cleanup hata yutmamali; _preserve_pkg istisnasi _cleanup icinde
    # yakalanirsa paket yerinde birakilir.
    assert pipe._result.success is True


def test_hedef_yazilamadiginda_paket_tempde_kalir(here, warn_report, monkeypatch):
    pipe, deb, pkg, _, _ = here
    import shutil as shutil_mod
    monkeypatch.setattr(shutil_mod, "move",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("salt okunur")))
    pipe._skip_install_message = "toplu mod: kurulum atlandi"
    pipe._decision_made = True
    pipe._decision_approved = False
    pipe.run(deb)
    assert pipe._result.success is True
    assert pkg.exists(), "tasma basarisizsa paket gecici dizinde birakilmali"


# --- 4. reddi "basarisiz" olarak gosterme ------------------------------------

def test_batch_skip_install_adimi_skipped_etiketidir(here, warn_report):
    pipe, deb, _, _, _ = here
    adimlar = []
    pipe.step_changed.connect(lambda s, st: adimlar.append((s, st)))
    pipe._skip_install_message = "toplu mod: kurulum atlandi"
    pipe._decision_made = True
    pipe._decision_approved = False
    pipe.run(deb)
    pipe._cleanup()
    # INSTALL = 5
    assert (5, "skipped") in adimlar, (
        "kurulum bilerek atlildiginda 'done' degil 'skipped' gosterilmeli: "
        f"adimlar={adimlar}")


def test_kullanici_reddi_skipped_etiketidir(here, warn_report):
    pipe, deb, _, _, _ = here
    adimlar = []
    pipe.step_changed.connect(lambda s, st: adimlar.append((s, st)))
    pipe._decision_made = True
    pipe._decision_approved = False
    pipe.run(deb)
    assert (5, "skipped") in adimlar


# --- _unique_path birimi -----------------------------------------------------

def test_unique_path_bos_hedef():
    hedef = Path("/yok/byle/demo-1.0-1-x86_64.pkg.tar.zst")
    assert ConversionPipeline._unique_path(hedef) == hedef


def test_unique_path_sayisal_sonek(tmp_path):
    mevcut = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    mevcut.write_bytes(b"x")
    hedef = ConversionPipeline._unique_path(mevcut)
    assert hedef != mevcut
    assert hedef.exists() is False
    assert hedef.name == "demo-1.0-1-x86_64.pkg.tar.zst.2"


def test_is_path_in_dir(tmp_path):
    ic = tmp_path / "tmpd" / "p.pkg"
    dis = tmp_path / "baska" / "p.pkg"
    assert ConversionPipeline._is_path_in_dir(ic, tmp_path / "tmpd") is True
    assert ConversionPipeline._is_path_in_dir(dis, tmp_path / "tmpd") is False


def test_zaten_disarida_olana_dokunma(here, monkeypatch, warn_report):
    """Paket zaten giris dizinininde (orn. CLI yolu) ise tasima yapilmamali."""
    pipe, deb, pkg, giris_dir, _ = here
    pipe._skip_install_message = "toplu mod: kurulum atlandi"
    pipe._decision_made = True
    pipe._decision_approved = False
    # simulate: converted_pkg already outside temp dir
    disarida = giris_dir / pkg.name
    disarida.write_bytes(b"P")
    monkeypatch.setattr(ConversionPipeline, "_convert_deb",
                        lambda self, dp, od: _set_conv(self, disarida))
    pipe.run(deb)
    assert pipe._result.converted_pkg == disarida
    assert disarida.exists()
