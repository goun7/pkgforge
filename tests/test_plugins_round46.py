"""Tur-46 — plugin/secret kalan satirlari."""
from __future__ import annotations

import shutil as shutil_mod
import subprocess  # noqa: F401
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import core.plugins as CP
import core.plugins.deb_to_rpm_plugin as D2R
import core.plugins.rpm_to_deb_plugin as R2D
import core.secrets_store as SS

ARACLAR = NS(bsdtar="bsdtar")


# --- deb_to_rpm tam akis ----------------------------------------------------------

def test_deb_to_rpm_plugin_paths(monkeypatch, tmp_path):
    deb = tmp_path / "giris.deb"
    deb.write_bytes(b"D")
    cikti = tmp_path / "cikti"

    monkeypatch.setattr(D2R, "safe_run",
                        lambda *a, **k: NS(returncode=1,
                                           stderr=b"derleme patladi"))

    # alien yok (33 False + 52-54)
    monkeypatch.setattr(shutil_mod, "which", lambda n: None)
    eklenti = D2R.DebToRpmConverter()
    assert eklenti.is_available(ARACLAR) is False                  # 33
    ok, mesaj, yol = eklenti.convert(deb, cikti, ARACLAR)
    assert ok is False and "alien bulunamad" in mesaj              # 53-54

    # alien var ama rc!=0 (64-66)
    monkeypatch.setattr(shutil_mod, "which",
                        lambda n: "/usr/bin/alien" if n == "alien" else None)
    assert eklenti.is_available(ARACLAR) is True                   # 33 True
    ok, mesaj, _yol = eklenti.convert(deb, cikti, ARACLAR)
    assert ok is False and "alien başarısız" in mesaj              # 64-66

    # rc=0 ama rpm dosyasi uretilmedi (69-71)
    monkeypatch.setattr(D2R, "safe_run",
                        lambda *a, **k: NS(returncode=0, stdout="", stderr=b""))
    ok, mesaj, _yol = eklenti.convert(deb, cikti, ARACLAR)
    assert ok is False and "oluşturulamadı" in mesaj               # 70-71

    # basari yolu (73-75): safe_run icinde rpm olustur
    def uret(cmd, cwd=None, timeout=0, **k):
        Path(cwd).mkdir(parents=True, exist_ok=True)
        hedef = Path(cwd) / "sonuc.rpm"
        hedef.write_bytes(b"RPM")
        return NS(returncode=0, stdout="", stderr=b"")
    monkeypatch.setattr(D2R, "safe_run", uret)
    ok, mesaj, yol = eklenti.convert(deb, cikti, ARACLAR)
    assert ok is True and yol is not None and yol.name == "sonuc.rpm"  # 74-75


def test_rpm_to_deb_is_available(monkeypatch):
    eklenti = R2D.RpmToDebConverter()
    monkeypatch.setattr(shutil_mod, "which", lambda n: None)
    assert eklenti.is_available(ARACLAR) is False                  # R2D:33
    monkeypatch.setattr(shutil_mod, "which", lambda n: "/x/alien")
    assert eklenti.is_available(ARACLAR) is True


# --- plugins/__init__ dallari -------------------------------------------------------

def test_load_plugins_skip_pkg_and_underscore(monkeypatch):
    sahte_moduller = [("_gizli", False), ("paket_turu", True),
                      ("deb_plugin", False)]

    def sahte_iter(klasorler):
        return [(None, ad, paket) for ad, paket in sahte_moduller]

    monkeypatch.setattr(CP.pkgutil, "iter_modules", sahte_iter)
    # gercek import denemesi yapmasin: importlib'i kilitleyip beklenmedik
    # modul yuklemesini engelle — sadece bilinen girdiler continue etmeli
    def yasak_import(ad):
        raise AssertionError(f"beklenmeyen import: {ad}")
    monkeypatch.setattr(CP.importlib, "import_module", yasak_import)

    class SahteMarketYolu:
        def exists(self):
            return False

    import core.plugins.marketplace as MK
    monkeypatch.setattr(MK, "PLUGIN_DIR", SahteMarketYolu())
    yuklenen = CP.load_plugins()                                   # 104-106
    assert isinstance(yuklenen, dict)


def test_marketplace_already_loaded_skip(monkeypatch, tmp_path):
    py = tmp_path / "ornek.py"
    py.write_text("X = 1\n")

    class SahteMarketYolu:
        def exists(self):
            return True

        def glob(self, desen):
            return [py]

    import core.plugins.marketplace as MK
    monkeypatch.setattr(MK, "PLUGIN_DIR", SahteMarketYolu())

    yuklenen = CP.load_plugins()
    assert isinstance(yuklenen, dict)


def test_sighup_win32_return(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    CP._setup_sighup_handler()                                     # 240-241


# --- secrets_store close-OSError yutma ----------------------------------------------

def test_secret_store_close_oserror_swallowed(monkeypatch):
    class PatlakBaglanti:
        def close(self):
            raise OSError("soket kapandi")

    class Mağaza(SS.SecretStore):
        def _conn(self):
            return PatlakBaglanti()

        def _open_session(self, conn):
            return "/org/freedesktop/secrets/session/s1"

    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/x")
    monkeypatch.setattr(SS, "SecretStore", Mağaza)
    assert SS.available() is True                                  # 74-79