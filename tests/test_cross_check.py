"""Coverage itmesi — core/cross_check.py (kanal-tesi surum karsilastirma)."""
from __future__ import annotations

from types import SimpleNamespace

from core import cross_check as CC


def _cmp(a, b):
    # Basit sayisal karsilastirma (vercmp yerine deterministik).
    return (a > b) - (a < b)


def _aur(version, status="found"):
    return SimpleNamespace(status=status, aur_version=version)


def test_recommends_local_when_newest(monkeypatch):
    monkeypatch.setattr(CC, "check_aur", lambda n, v: _aur("1.0"))
    monkeypatch.setattr(CC, "_version_compare", _cmp)
    monkeypatch.setattr(CC, "_query_flatpak_version", lambda n: "")
    rep = CC.cross_check_package("pkg", "2.0")
    assert rep.recommended_source == "local"


def test_recommends_aur_when_newer(monkeypatch):
    monkeypatch.setattr(CC, "check_aur", lambda n, v: _aur("3.0"))
    monkeypatch.setattr(CC, "_version_compare", _cmp)
    monkeypatch.setattr(CC, "_query_flatpak_version", lambda n: "")
    rep = CC.cross_check_package("pkg", "1.0")
    assert rep.recommended_source == "aur"
    assert rep.aur_version == "3.0"


def test_recommends_flatpak_when_newest(monkeypatch):
    monkeypatch.setattr(CC, "check_aur", lambda n, v: _aur("2.0"))
    monkeypatch.setattr(CC, "_version_compare", _cmp)
    monkeypatch.setattr(CC, "_query_flatpak_version", lambda n: "9.0")
    rep = CC.cross_check_package("pkg", "1.0")
    assert rep.recommended_source == "flatpak"
    assert rep.flatpak_version == "9.0"


def test_aur_not_found_yields_empty(monkeypatch):
    monkeypatch.setattr(CC, "check_aur", lambda n, v: _aur("", "not_found"))
    monkeypatch.setattr(CC, "_version_compare", _cmp)
    monkeypatch.setattr(CC, "_query_flatpak_version", lambda n: "")
    rep = CC.cross_check_package("pkg", "1.0")
    assert rep.aur_version == ""
    assert rep.recommended_source == "local"


def test_flatpak_version_empty_without_binary(monkeypatch):
    monkeypatch.setattr(CC.shutil, "which", lambda x: None)
    assert CC._query_flatpak_version("pkg") == ""


def test_flatpak_version_empty_for_blank_name(monkeypatch):
    assert CC._query_flatpak_version("") == ""
