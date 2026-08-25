"""Coverage itmesi — core/flatpak_converter.py listeleme/donusum/manifest."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS

import core.flatpak_converter as FC
from core.flatpak_converter import FlatpakApp, _estimate_size_mb

TAB = chr(9)


def _ns(code, out="", err=""):
    return NS(returncode=code, stdout=out, stderr=err)


def test_availability(monkeypatch):
    monkeypatch.setattr(FC.shutil, "which", lambda n: None)
    assert FC.is_flatpak_available() is False
    monkeypatch.setattr(FC.shutil, "which", lambda n: "/usr/bin/flatpak")
    assert FC.is_flatpak_available() is True


def test_list_installed_parse(monkeypatch):
    monkeypatch.setattr(FC.shutil, "which", lambda n: None)
    assert FC.list_installed_apps() == []

    monkeypatch.setattr(FC.shutil, "which", lambda n: "/usr/bin/flatpak")
    rows = TAB.join(["org.a.A", "A Uygulama", "2.0", "stable",
                     "aciklama", "flathub"])
    rows2 = TAB.join(["org.b.B", "", "", "stable", ""])
    monkeypatch.setattr(FC, "safe_run",
                        lambda cmd, timeout=None: _ns(0, out=rows + chr(10) + rows2))
    apps = FC.list_installed_apps()
    assert len(apps) == 2
    assert apps[0].app_id == "org.a.A" and apps[0].version == "2.0"
    assert apps[0].origin == "flathub"
    assert apps[1].name == "org.b.B" and apps[1].version == "1.0"
    assert apps[1].branch == "stable"


def test_get_app_info(monkeypatch):
    monkeypatch.setattr(FC, "list_installed_apps", lambda: [
        FlatpakApp("org.x.X", "X", "1", "stable")])
    assert FC.get_app_info("org.x.X").name == "X"
    assert FC.get_app_info("org.y.Y") is None


def test_export_app_files_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(FC.shutil, "which", lambda n: None)
    assert FC.export_app_files("org.z.Z", tmp_path / "e") is False

    monkeypatch.setattr(FC.shutil, "which", lambda n: "/usr/bin/flatpak")
    calls = []

    def fake_run(cmd, timeout=None, **kw):
        calls.append(list(cmd))
        return _ns(1)
    monkeypatch.setattr(FC, "safe_run", fake_run)
    assert FC.export_app_files("org.z.Z", tmp_path / "e2") is False

    app_root = tmp_path / "app"
    (app_root / "files" / "bin").mkdir(parents=True)
    (app_root / "files" / "bin" / "tool").write_bytes(b"x")

    def fake_ok(cmd, timeout=None, **kw):
        calls.append(list(cmd))
        return _ns(0, out=str(app_root) + chr(10))
    monkeypatch.setattr(FC, "safe_run", fake_ok)
    dest = tmp_path / "export"
    assert FC.export_app_files("org.z.Z", dest) is True
    assert (dest / "opt" / "org.z.Z" / "bin" / "tool").is_file()


def test_estimate_size_mb(tmp_path):
    assert _estimate_size_mb(tmp_path) == 1


def _app():
    return FlatpakApp("org.demo.Demo", "Demo", "3.2", "stable", "Aciklama")


def test_create_deb_package(monkeypatch, tmp_path):
    ok = FC.create_deb_package(_app(), tmp_path / "yok", tmp_path / "a.deb")
    assert ok[0] is False and "bulunamadı" in ok[1]

    files = tmp_path / "files"
    files.mkdir()
    (files / "run.sh").write_text("echo merhaba")
    monkeypatch.setattr(FC.shutil, "which", lambda n: "/usr/bin/dpkg-deb")
    monkeypatch.setattr(FC, "safe_run",
                        lambda cmd, timeout=None: Path(cmd[-1]).write_bytes(b"DEB")
                        or NS(0)) if False else None

    def fake_dpkg(cmd, timeout=None, **kw):
        Path(cmd[-1]).write_bytes(b"DEB")
        return _ns(0)
    monkeypatch.setattr(FC, "safe_run", fake_dpkg)
    out = tmp_path / "demo.deb"
    r = FC.create_deb_package(_app(), files, out)
    assert r[0] is True and "hazır" in r[1] and out.is_file()

    monkeypatch.setattr(FC, "safe_run",
                        lambda cmd, timeout=None, **kw: _ns(2, err="kırık"))
    r2 = FC.create_deb_package(_app(), files, tmp_path / "b.deb")
    assert r2[0] is False and "başarısız" in r2[1]


def test_flatpak_to_deb_guards(monkeypatch, tmp_path):
    monkeypatch.setattr(FC.shutil, "which", lambda n: None)
    r = FC.flatpak_to_deb("org.a.A", tmp_path)
    assert r[0] is False and "flatpak bulunamadı" in r[1]


def test_flatpak_to_deb_happy(monkeypatch, tmp_path):
    out_dir = tmp_path / "cikti"
    monkeypatch.setattr(FC, "list_installed_apps", lambda: [_app()])

    def fake_export(app_id, export_dir, branch="stable"):
        export_dir.mkdir(parents=True)
        (export_dir / "calistir.sh").write_text("#!/bin/sh")
        return True
    monkeypatch.setattr(FC, "export_app_files", fake_export)
    monkeypatch.setattr(FC.shutil, "which", lambda n: "/usr/bin/dpkg-deb")

    def fake_dpkg(cmd, timeout=None, **kw):
        Path(cmd[-1]).write_bytes(b"DEB")
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(FC, "safe_run", fake_dpkg)
    ok, msg, deb = FC.flatpak_to_deb("org.demo.Demo", out_dir)
    assert ok is True and deb.is_file()
    assert deb.name == "org-demo-demo_3.2_amd64.deb"


def test_runtime_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(FC.shutil, "which", lambda n: None)
    r0 = FC.export_flatpak_runtime("org.demo.Demo", tmp_path)
    assert r0[0] is False

    monkeypatch.setattr(FC.shutil, "which", lambda n: "/usr/bin/flatpak")
    monkeypatch.setattr(FC, "list_installed_apps", lambda: [_app()])
    ok, msg, path = FC.export_flatpak_runtime(
        "org.yok.Yok", tmp_path)
    assert ok is False and "bulunamadı" in msg

    ok2, msg2, mf = FC.export_flatpak_runtime(
        "org.demo.Demo", tmp_path, branch="beta")
    assert ok2 is True and mf.is_file()
    data = json.loads(mf.read_text())
    assert data["app-id"] == "org.demo.Demo"
    assert data["runtime"] == "org.freedesktop.Platform"
    assert data["modules"][0]["name"] == "Demo"
    assert data["_pkgforge"]["original_version"] == "3.2"
    assert "beta" in data["modules"][0]["sources"][0]["branch"]
