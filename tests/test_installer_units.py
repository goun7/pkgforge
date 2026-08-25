"""Coverage itmesi — core/installer.py guardlar ve sonuc dallari."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication

import core.installer as INS
from core.installer import Installer, _find_install_helper


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def test_find_install_helper_points_at_source():
    p = _find_install_helper()
    assert isinstance(p, Path) and p.name == "install_helper.sh"


def _spy(qt_app_inst):
    got = []
    qt_app_inst.finished.connect(lambda ok, msg: got.append((ok, msg)))
    lines = []
    qt_app_inst.output_line.connect(lambda s: lines.append(s))
    return got, lines


def _tools(pkexec="/usr/bin/pkexec", pacman="/usr/bin/pacman"):
    return NS(pkexec=pkexec, pacman=pacman)


def test_install_missing_pkg_emits_failure(qapp, tmp_path):
    inst = Installer(_tools())
    got, _lines = _spy(inst)
    inst.install(tmp_path / "yok.pkg.tar.zst", "demo")
    assert got == [(False, got[0][1])] and "bulunamadı" in got[0][1]


def test_install_without_pkexec(qapp, tmp_path):
    f = tmp_path / "x.pkg.tar.zst"
    f.write_bytes(b"x")
    inst = Installer(_tools(pkexec=""))
    got, _l = _spy(inst)
    inst.install(f, "demo")
    assert got[0][0] is False and "polkit" in got[0][1]


def test_install_invalid_extension(qapp, tmp_path):
    f = tmp_path / "arsiv.zip"
    f.write_bytes(b"x")
    inst = Installer(_tools())
    got, _l = _spy(inst)
    inst.install(f, "demo")
    assert got[0][0] is False and "Geçersiz" in got[0][1]


def _mk_installer(qapp):
    return Installer(_tools())


def test_on_finished_cancelled(qapp):
    inst = _mk_installer(qapp)
    got, _l = _spy(inst)
    inst._cancelled = True
    inst._on_finished(0, None)
    assert got[0][0] is False and "iptal" in got[0][1].lower()


def test_on_finished_exit_codes(qapp):
    inst = _mk_installer(qapp)
    got, _l = _spy(inst)
    inst._snapshot_name = "snap-1"
    inst._pkg_name = "demo"
    inst._process = NS(state=lambda: None) if False else None
    inst._on_finished(126, None)
    assert "Polkit" in got[-1][1] and "snap-1" in got[-1][1]
    inst._on_finished(127, None)
    assert "pkexec komutu bulunamadı" in got[-1][1]
    inst._on_finished(9, None)
    assert "kod: 9" in got[-1][1]


def test_on_finished_success_verified(monkeypatch, qapp):
    inst = _mk_installer(qapp)
    got, lines = _spy(inst)
    inst._pkg_name = "demo"
    inst._snapshot_name = "snap-x"
    monkeypatch.setattr(INS, "safe_run",
                        lambda cmd, timeout=None: NS(returncode=0))
    inst._on_finished(0, None)
    assert got[-1] == (True, "demo başarıyla kuruldu")
    assert any("snap-x" in s for s in lines)


def test_on_finished_success_unverified(monkeypatch, qapp):
    inst = _mk_installer(qapp)
    got, _l = _spy(inst)
    inst._pkg_name = "demo"
    monkeypatch.setattr(INS, "safe_run",
                        lambda cmd, timeout=None: NS(returncode=1))
    inst._on_finished(0, None)
    assert got[-1][0] is True and "doğrulama yapılamadı" in got[-1][1]


def test_verify_invalid_name_skips_pacman(monkeypatch):
    called = {"n": 0}

    def no_call(cmd, timeout=None):
        called["n"] += 1
        raise AssertionError("cagrilmamali")
    monkeypatch.setattr(INS, "safe_run", no_call)
    inst = _mk_installer(qapp)
    inst._pkg_name = "--dbpath=/etc"
    assert inst._verify_installation() is False
    assert called["n"] == 0
