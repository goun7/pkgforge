"""Coverage itmesi — core/appimage_converter.py cikarma/metadata/donusum."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import core.appimage_converter as AC


def _ns(code):
    return NS(returncode=code, stdout="", stderr="")


MAGIC = b"AI" + bytes([2])


def test_magic_and_availability(monkeypatch, tmp_path):
    assert AC.is_appimage_file(tmp_path / "yok.AppImage") is False
    f = tmp_path / "a.AppImage"
    f.write_bytes(b"ELF-not")
    assert AC.is_appimage_file(f) is False
    f.write_bytes(MAGIC)
    assert AC.is_appimage_file(f) is True
    monkeypatch.setattr(AC.shutil, "which", lambda n: "/usr/bin/unsquashfs")
    assert AC.is_appimage_available() is True


def test_parse_desktop_file(tmp_path):
    assert AC.parse_desktop_file(tmp_path / "yok.desktop") == {}
    d = tmp_path / "uyg.desktop"
    d.write_text("[Desktop Entry]" + chr(10) + "Name=Uygulama Adi"
                 + chr(10) + "X-AppImage-Version=2.5"
                 + chr(10) + "Comment=Kisa aciklama", encoding="utf-8")
    info = AC.parse_desktop_file(d)
    assert info["Name"] == "Uygulama Adi"
    assert info["X-AppImage-Version"] == "2.5"


def test_extract_builtin_then_unsquash(monkeypatch, tmp_path):
    f = tmp_path / "a.AppImage"
    f.write_bytes(MAGIC)
    dest = tmp_path / "cikis1"
    dest.mkdir()
    calls = []

    def fake_builtin(cmd, timeout=None, cwd=None, **kw):
        calls.append(Path(cmd[0]).name)
        Path(cwd, "squashfs-root").mkdir(parents=True)
        return _ns(0)
    monkeypatch.setattr(AC.os, "access", lambda p, m: True)
    monkeypatch.setattr(AC, "safe_run", fake_builtin)
    assert AC.extract_appimage(f, dest) is True
    assert calls == ["a.AppImage"]

    dest2 = tmp_path / "cikis2"
    dest2.mkdir()
    calls.clear()

    def fake_fallback(cmd, timeout=None, cwd=None, **kw):
        calls.append(Path(cmd[0]).name)
        Path(cmd[2]).mkdir(parents=True, exist_ok=True)
        return _ns(0)
    monkeypatch.setattr(AC.os, "access", lambda p, m: False)
    monkeypatch.setattr(AC.shutil, "which", lambda n: "/usr/bin/unsquashfs")
    monkeypatch.setattr(AC, "safe_run", fake_fallback)
    assert AC.extract_appimage(f, dest2) is True
    assert calls == ["unsquashfs"]


DESKTOP = ("[Desktop Entry]" + chr(10) + "Name=My Uygulama"
           + chr(10) + "X-AppImage-Version=3.1"
           + chr(10) + "Comment=Aciklama")


def _seed_unsquash(desktop_name="myapp.desktop"):
    def fake_unsquash(cmd, timeout=None, cwd=None, **kw):
        root = Path(cmd[2])
        root.mkdir(parents=True, exist_ok=True)
        if desktop_name:
            (root / desktop_name).write_text(DESKTOP, encoding="utf-8")
        (root / "AppRun").write_text("#!/bin/sh")
        (root / "usr").mkdir(exist_ok=True)
        (root / "usr" / "bin").mkdir(parents=True, exist_ok=True)
        (root / "usr" / "bin" / "myapp").write_bytes(b"x" * 2048)
        (root / "data.bin").write_bytes(b"d" * 1500)
        return _ns(0)
    return fake_unsquash


def test_get_info_from_desktop_and_fallback(monkeypatch, tmp_path):
    f = tmp_path / "MyApp-3.1.AppImage"
    f.write_bytes(MAGIC)
    monkeypatch.setattr(AC.os, "access", lambda p, m: False)
    monkeypatch.setattr(AC.shutil, "which", lambda n: "/usr/bin/unsquashfs")
    monkeypatch.setattr(AC, "safe_run", _seed_unsquash())
    info = AC.get_appimage_info(f)
    assert info.name == "My Uygulama" and info.version == "3.1"
    assert info.description == "Aciklama"
    assert "[Desktop Entry]" in info.desktop_file

    f2 = tmp_path / "SadeIsim.AppImage"
    f2.write_bytes(MAGIC)
    monkeypatch.setattr(AC, "safe_run", _seed_unsquash(""))
    info2 = AC.get_appimage_info(f2)
    assert info2.name == "SadeIsim" and info2.version == "1.0"


def test_convert_guards(monkeypatch, tmp_path):
    ok = AC.appimage_to_deb(tmp_path / "yok.AppImage", tmp_path)
    assert ok[0] is False and "bulunamadı" in ok[1]
    bad = tmp_path / "x.AppImage"
    bad.write_bytes(b"nope")
    r = AC.appimage_to_deb(bad, tmp_path)
    assert r[0] is False and "Geçersiz AppImage" in r[1]


def test_convert_happy_path(monkeypatch, tmp_path):
    f = tmp_path / "Tool-9.9.AppImage"
    f.write_bytes(MAGIC)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(AC.os, "access", lambda p, m: False)
    monkeypatch.setattr(AC.shutil, "which", lambda n: "/usr/bin/unsquashfs")
    seen = []

    def dispatch(cmd, timeout=None, cwd=None, **kw):
        if cmd[0] == "dpkg-deb":
            seen.append(list(cmd))
            Path(cmd[-1]).write_bytes(b"DEB")
            return _ns(0)
        return _seed_unsquash("")(cmd, timeout=timeout)
    monkeypatch.setattr(AC, "safe_run", dispatch)
    ok, msg, deb = AC.appimage_to_deb(f, out_dir)
    assert ok is True and deb.is_file()
    assert deb.name == "tool-9.9_1.0_amd64.deb"
