"""Coverage itmesi — cli donusturucu komutlari ve from-source."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import cli
import core.appimage_converter as AC
import core.flatpak_converter as FC
import core.rpm_to_deb_converter as RD


def test_flatpak_export_unavailable(capsys, monkeypatch):
    monkeypatch.setattr(FC, "is_flatpak_available", lambda: False)
    rc = cli._cmd_flatpak_export(NS(list=False, app_id=None))
    assert rc == 1 and "flatpak bulunamadı" in capsys.readouterr().out


def test_flatpak_export_list(monkeypatch, capsys):
    monkeypatch.setattr(FC, "is_flatpak_available", lambda: True)
    monkeypatch.setattr(FC, "list_installed_apps", list)
    rc = cli._cmd_flatpak_export(NS(list=True, app_id=None))
    assert rc == 0 and "bulunamadı" in capsys.readouterr().out

    apps = [NS(app_id="org.a.A", name="A", version="1", branch="stable")]
    monkeypatch.setattr(FC, "list_installed_apps", lambda: apps)
    rc2 = cli._cmd_flatpak_export(NS(list=True, app_id=None))
    out = capsys.readouterr().out
    assert rc2 == 0 and "org.a.A" in out


def test_flatpak_export_missing_id_and_fail(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(FC, "is_flatpak_available", lambda: True)
    rc = cli._cmd_flatpak_export(NS(list=False, app_id=None, output_dir=None))
    assert rc == 1 and "ID" in capsys.readouterr().out

    monkeypatch.setattr(FC, "flatpak_to_deb",
                        lambda a, o, b: (False, "koptu", None))
    rc2 = cli._cmd_flatpak_export(NS(
        list=False, app_id="org.x.X", output_dir=str(tmp_path)))
    assert rc2 == 1 and "koptu" in capsys.readouterr().out


def test_flatpak_export_success(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(FC, "is_flatpak_available", lambda: True)
    deb = tmp_path / "cikti.deb"
    monkeypatch.setattr(FC, "flatpak_to_deb",
                        lambda a, o, b: (True, "hazir", deb))
    rc = cli._cmd_flatpak_export(NS(
        list=False, app_id="org.x.X", output_dir=str(tmp_path)))
    assert rc == 0 and "dpkg -i" in capsys.readouterr().out


def test_appimage_export_guards(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(AC, "is_appimage_available", lambda: False)
    rc = cli._cmd_appimage_export(NS(appimage="x", output_dir=None))
    assert rc == 1 and "unsquashfs" in capsys.readouterr().out

    monkeypatch.setattr(AC, "is_appimage_available", lambda: True)
    rc2 = cli._cmd_appimage_export(NS(
        appimage=str(tmp_path / "yok.AppImage"), output_dir=None))
    assert rc2 == 1 and "bulunamadı" in capsys.readouterr().out


def test_appimage_export_paths(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(AC, "is_appimage_available", lambda: True)
    f = tmp_path / "a.AppImage"
    f.write_bytes(b"x")
    monkeypatch.setattr(AC, "appimage_to_deb",
                        lambda p, o: (False, "cikaramadi", None))
    rc = cli._cmd_appimage_export(NS(
        appimage=str(f), output_dir=str(tmp_path)))
    assert rc == 1 and "cikaramadi" in capsys.readouterr().out

    deb = tmp_path / "a.deb"
    monkeypatch.setattr(AC, "appimage_to_deb", lambda p, o: (True, "hazir", deb))
    rc2 = cli._cmd_appimage_export(NS(
        appimage=str(f), output_dir=str(tmp_path)))
    assert rc2 == 0 and "dpkg -i" in capsys.readouterr().out


def test_rpm_to_deb_guards(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(RD, "is_rpm_to_deb_available", lambda: False)
    rc = cli._cmd_rpm_to_deb(NS(rpm="x", output_dir=None))
    assert rc == 1 and "rpm2cpio" in capsys.readouterr().out

    monkeypatch.setattr(RD, "is_rpm_to_deb_available", lambda: True)
    rc2 = cli._cmd_rpm_to_deb(NS(
        rpm=str(tmp_path / "yok.rpm"), output_dir=None))
    assert rc2 == 1 and "bulunamadı" in capsys.readouterr().out


def test_rpm_to_deb_paths(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(RD, "is_rpm_to_deb_available", lambda: True)
    f = tmp_path / "p.rpm"
    f.write_bytes(b"x")
    monkeypatch.setattr(RD, "rpm_to_deb", lambda p, o: (True, "hazir", tmp_path / "d.deb"))
    rc = cli._cmd_rpm_to_deb(NS(rpm=str(f), output_dir=str(tmp_path)))
    assert rc == 0 and "hazir" in capsys.readouterr().out

    monkeypatch.setattr(RD, "rpm_to_deb", lambda p, o: (False, "hata", None))
    rc2 = cli._cmd_rpm_to_deb(NS(rpm=str(f), output_dir=str(tmp_path)))
    assert rc2 == 1 and "hata" in capsys.readouterr().out


def _fake_clone(files):
    def fake(cmd, timeout=None, **kw):
        repo = Path(cmd[4])
        repo.mkdir(parents=True)
        for name in files:
            (repo / name).write_text("demo")
        return NS(returncode=0, stdout="", stderr="")
    return fake


def _from_source(monkeypatch, capsys, tmp_path, files, content="# PKGBUILD"):
    import core.from_source as FSRC
    monkeypatch.setattr(cli, "safe_run", _fake_clone(files))
    monkeypatch.setattr(FSRC, "generate_pkgbuild_from_source",
                        lambda name, url, bs, rd: content)
    args = NS(repo_url="https://github.com/deneme/proje", output_dir=str(tmp_path))
    return cli._cmd_from_source(args)


def test_from_source_clone_fail(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "safe_run", lambda cmd, timeout=None, **kw:
                        NS(returncode=1, stdout="", stderr="ag hatasi"))
    rc = cli._cmd_from_source(NS(
        repo_url="https://github.com/d/x", output_dir=str(tmp_path)))
    assert rc == 1 and "clone" in capsys.readouterr().out.lower()


def test_from_source_cmake_and_unknown(capsys, monkeypatch, tmp_path):
    rc = _from_source(monkeypatch, capsys, tmp_path, ["CMakeLists.txt"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "cmake" in out and "proje" in out
    assert (tmp_path / "PKGBUILD-proje").is_file()

    rc2 = _from_source(monkeypatch, capsys, tmp_path, [])
    assert rc2 == 0 and "unknown" in capsys.readouterr().out


def test_from_source_all_systems(capsys, monkeypatch, tmp_path):
    for files, expected in ([
        (["meson.build"], "meson"),
        (["Cargo.toml"], "cargo"),
        (["configure"], "autotools"),
        (["Makefile"], "make"),
        (["setup.py"], "python"),
    ]):
        rc = _from_source(monkeypatch, capsys, tmp_path, files)
        assert rc == 0 and expected in capsys.readouterr().out, files
