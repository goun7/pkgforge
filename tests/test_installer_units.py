"""Coverage itmesi — core/installer.py guardlar ve sonuc dallari."""
from __future__ import annotations

import sys
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
    assert got[0] == (False, "pkexec bulunamadı — polkit paketi gerekli")


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
    got, lines = _spy(inst)
    inst._pkg_name = "demo"
    monkeypatch.setattr(INS, "safe_run",
                        lambda cmd, timeout=None: NS(returncode=1))
    inst._on_finished(0, None)
    assert got[-1] == (True, "Kurulum tamamlandı (doğrulama yapılamadı)")
    assert "⚠ Kurulum tamamlandı ama doğrulama başarısız" in lines


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

# ══════════════════════════════════════════════════════════════════
# Tur-64 mutmut kampanyasi — hayatta kalan 111 mutanti oldur.
# FakeProcess + kesin assert'ler ile install/snapshot/cancel/output/
# error/find_helper/init/verify dallari tam korunur.
# ══════════════════════════════════════════════════════════════════
import logging

from PyQt6.QtCore import QObject, QProcess


class FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, fn):
        self.connected.append(fn)


class FakeByteArray:
    def __init__(self, data: bytes):
        self._data = data

    def data(self) -> bytes:
        return self._data


class FakeProcess:
    def __init__(self, parent=None):
        self.channel_mode = None
        self.readyReadStandardOutput = FakeSignal()
        self.finished = FakeSignal()
        self.errorOccurred = FakeSignal()
        self.started = []
        self.killed = False
        self._state = QProcess.ProcessState.NotRunning
        self._out = b""

    def setProcessChannelMode(self, mode):
        self.channel_mode = mode

    def start(self, program, args):
        self.started.append((program, list(args)))

    def state(self):
        return self._state

    def kill(self):
        self.killed = True

    def readAllStandardOutput(self):
        return FakeByteArray(self._out)


def _mk(qapp, tmp_path, factory, helper_exists=True):
    """Installer + FakeProcess + spy; INSTALL_HELPER ve snapshot kapali."""
    helper = tmp_path / "install_helper.sh"
    if helper_exists:
        helper.write_text("#!/bin/bash")
    inst = Installer(_tools(), process_factory=factory)
    got, lines = _spy(inst)
    return inst, got, lines, helper


# ── __init__ (9 mutant) ─────────────────────────────────────────
def test_init_defaults(qapp):
    inst = Installer(_tools())
    assert inst._process is None
    assert inst._pkg_name == ""
    assert inst._cancelled is False
    assert inst._snapshot_name == ""
    assert inst._make_process == Installer._default_process


def test_init_factory_and_parent(qapp):
    parent = QObject()
    fac = lambda p: FakeProcess(p)
    inst = Installer(_tools(), parent=parent, process_factory=fac)
    assert inst._make_process is fac
    assert inst.parent() is parent


# ── install mutlu yol: helper dali (install mutantlari) ─────────
def test_install_happy_helper(qapp, tmp_path, monkeypatch):
    import i18n
    monkeypatch.setattr(i18n, "load_setting", lambda k, d=None: False)
    fp = FakeProcess()
    seen = {}

    def fac(p):
        seen["parent"] = p
        return fp

    inst, _got, lines, helper = _mk(qapp, tmp_path, fac)
    monkeypatch.setattr(INS, "INSTALL_HELPER", helper)
    pkg = tmp_path / "demo.pkg.tar.zst"
    pkg.write_bytes(b"x")
    inst.install(pkg, "demo")
    assert inst._pkg_name == "demo"
    assert inst._cancelled is False
    assert inst._process is fp
    assert seen["parent"] is inst
    assert fp.channel_mode == QProcess.ProcessChannelMode.MergedChannels
    assert fp.readyReadStandardOutput.connected == [inst._on_output]
    assert fp.finished.connected == [inst._on_finished]
    assert fp.errorOccurred.connected == [inst._on_error]
    assert fp.started == [("/usr/bin/pkexec", [str(helper), str(pkg)])]
    assert f"▶ Paket kuruluyor: {pkg.name}" in lines
    assert "  Yetki yükseltme isteniyor (Polkit)..." in lines


def test_install_happy_fallback(qapp, tmp_path, monkeypatch):
    import i18n
    monkeypatch.setattr(i18n, "load_setting", lambda k, d=None: False)
    fp = FakeProcess()
    inst, _got, _lines, _helper = _mk(qapp, tmp_path, lambda p: fp, helper_exists=False)
    monkeypatch.setattr(INS, "INSTALL_HELPER", tmp_path / "yok_helper.sh")
    pkg = tmp_path / "demo.pkg.tar.zst"
    pkg.write_bytes(b"x")
    inst.install(pkg, "demo")
    assert fp.started == [(
        "/usr/bin/pkexec",
        ["/usr/bin/pacman", "-U", "--noconfirm", "--", str(pkg)],
    )]

# ── install snapshot blogu (tek-diyalog sozlesmesi) ─────────────
# Kurulum snapshot'i ayri take_snapshot cagrisi degil, helper'a
# --snapshot bayragidir. Testler argv sozlesmesini kilitler.
def _snap_setup(monkeypatch, backend, ad="snap-9"):
    import core.snapshot_manager as SM
    import i18n
    calls = {"load_setting": [], "snapshot_name": []}

    def ls(k, d=None):
        calls["load_setting"].append((k, d))
        return True

    def sn(label):
        calls["snapshot_name"].append(label)
        return ad

    monkeypatch.setattr(i18n, "load_setting", ls)
    monkeypatch.setattr(SM, "detect_backend", lambda: backend)
    monkeypatch.setattr(SM, "snapshot_name", sn)
    return calls


def test_install_snapshot_success(qapp, tmp_path, monkeypatch):
    fp = FakeProcess()
    inst, _got, lines, helper = _mk(qapp, tmp_path, lambda p: fp)
    monkeypatch.setattr(INS, "INSTALL_HELPER", helper)
    calls = _snap_setup(monkeypatch, "btrfs")
    pkg = tmp_path / "demo.pkg.tar.zst"
    pkg.write_bytes(b"x")
    inst.install(pkg, "demo")
    assert inst._snapshot_name == ""
    assert ("snapshot", True) in calls["load_setting"]
    assert calls["snapshot_name"] == ["demo"]
    assert fp.started == [("/usr/bin/pkexec",
                            [str(helper), "--snapshot", "snap-9", str(pkg)])]
    # helper snapshot-ok satiri gorunce ad kaydedilir + bilgi basilir
    fp._out = b"snapshot-ok: /snap-9\n"
    inst._on_output()
    assert inst._snapshot_name == "/snap-9"
    assert any("Snapshot hazır: /snap-9" in s for s in lines)


def test_install_snapshot_fail(qapp, tmp_path, monkeypatch, caplog):
    fp = FakeProcess()
    inst, _got, _lines, helper = _mk(qapp, tmp_path, lambda p: fp)
    monkeypatch.setattr(INS, "INSTALL_HELPER", helper)
    import core.snapshot_manager as SM
    import i18n
    monkeypatch.setattr(i18n, "load_setting", lambda k, d=None: True)
    monkeypatch.setattr(SM, "detect_backend", lambda: "btrfs")
    boom = RuntimeError("snap-patladi")
    monkeypatch.setattr(SM, "snapshot_name", lambda label: (_ for _ in ()).throw(boom))
    pkg = tmp_path / "demo.pkg.tar.zst"
    pkg.write_bytes(b"x")
    with caplog.at_level(logging.DEBUG, logger="core.installer"):
        inst.install(pkg, "demo")
    assert inst._snapshot_name == ""
    # bayrak dusurulur, kurulum devam eder
    assert fp.started == [("/usr/bin/pkexec", [str(helper), str(pkg)])]
    recs = [r for r in caplog.records if "temizleme" in r.getMessage().lower()]
    assert recs and recs[0].msg == "Snapshot temizleme başarısız: %s"
    assert boom in recs[0].args


def test_install_snapshot_backend_none(qapp, tmp_path, monkeypatch):
    fp = FakeProcess()
    inst, _got, _lines, helper = _mk(qapp, tmp_path, lambda p: fp)
    monkeypatch.setattr(INS, "INSTALL_HELPER", helper)
    _snap_setup(monkeypatch, "none")
    pkg = tmp_path / "demo.pkg.tar.zst"
    pkg.write_bytes(b"x")
    inst.install(pkg, "demo")
    assert inst._snapshot_name == ""
    assert fp.started == [("/usr/bin/pkexec", [str(helper), str(pkg)])]


def test_install_snapshot_setting_off(qapp, tmp_path, monkeypatch):
    import core.snapshot_manager as SM
    import i18n
    called = {"n": 0}
    fp = FakeProcess()
    inst, _got, _lines, helper = _mk(qapp, tmp_path, lambda p: fp)
    monkeypatch.setattr(INS, "INSTALL_HELPER", helper)
    monkeypatch.setattr(i18n, "load_setting", lambda k, d=None: False)

    def no_snap(label):
        called["n"] += 1
        return "snap-x"

    monkeypatch.setattr(SM, "snapshot_name", no_snap)
    pkg = tmp_path / "demo.pkg.tar.zst"
    pkg.write_bytes(b"x")
    inst.install(pkg, "demo")
    assert inst._snapshot_name == ""
    assert called["n"] == 0
    assert fp.started == [("/usr/bin/pkexec", [str(helper), str(pkg)])]


# ── cancel / _on_output / _on_error / _default_process ─────────
def test_cancel_running(qapp):
    inst = Installer(_tools())
    _got, lines = _spy(inst)
    fp = FakeProcess()
    fp._state = QProcess.ProcessState.Running
    inst._process = fp
    inst.cancel()
    assert inst._cancelled is True
    assert fp.killed is True
    assert "⚠ Kurulum iptal edildi" in lines


def test_cancel_not_running(qapp):
    inst = Installer(_tools())
    lines = []
    inst.output_line.connect(lambda s: lines.append(s))
    fp = FakeProcess()
    fp._state = QProcess.ProcessState.NotRunning
    inst._process = fp
    inst.cancel()
    assert inst._cancelled is True
    assert fp.killed is False


def test_cancel_no_process(qapp):
    inst = Installer(_tools())
    inst._process = None
    inst.cancel()
    assert inst._cancelled is True


def test_on_output_emits_lines(qapp):
    inst = Installer(_tools())
    lines = []
    inst.output_line.connect(lambda s: lines.append(s))
    fp = FakeProcess()
    fp._out = b"satir1\n\nsatir2\n"
    inst._process = fp
    inst._on_output()
    assert "  satir1" in lines and "  satir2" in lines


def test_on_output_no_process(qapp):
    inst = Installer(_tools())
    inst._process = None
    inst._on_output()  # patlamaz


def test_on_output_invalid_bytes_replaced(qapp):
    inst = Installer(_tools())
    lines = []
    inst.output_line.connect(lambda s: lines.append(s))
    fp = FakeProcess()
    fp._out = b"\xff\xfe gecersiz"
    inst._process = fp
    inst._on_output()  # errors="replace" ile patlamaz
    assert len(lines) == 1


def test_on_error_map(qapp):
    inst = Installer(_tools())
    got, _l = _spy(inst)
    inst._on_error(QProcess.ProcessError.FailedToStart)
    assert got[-1] == (False, "pkexec başlatılamadı")
    inst._on_error(QProcess.ProcessError.Crashed)
    assert got[-1] == (False, "Kurulum işlemi çöktü")
    inst._on_error(QProcess.ProcessError.Timedout)
    assert got[-1] == (False, "Kurulum zaman aşımı")


def test_on_error_unknown(qapp):
    inst = Installer(_tools())
    got, _l = _spy(inst)
    err = QProcess.ProcessError.ReadError
    inst._on_error(err)
    assert got[-1] == (False, f"Kurulum hatası: {err}")


def test_default_process_returns_qprocess(qapp):
    parent = QObject()
    p = Installer._default_process(parent)
    assert isinstance(p, QProcess)
    assert p.parent() is parent

# ── _find_install_helper (13 mutant): aday yolu dallari ─────────
def _src_helper_path():
    return Path(INS.__file__).resolve().parent.parent / "scripts" / "install_helper.sh"


def test_find_helper_source_exact(qapp, monkeypatch):
    # Sistem + sys.prefix kopyalari yoksa kaynak agaca dusulur.
    import pathlib
    real = pathlib.Path.is_file

    def fake_is_file(self):
        s = str(self)
        if s.startswith(("/usr/share/pkgforge", sys.prefix)):
            return False
        return real(self)

    monkeypatch.setattr(pathlib.Path, "is_file", fake_is_file)
    assert _find_install_helper() == _src_helper_path()


def test_find_helper_sysprefix(qapp, monkeypatch):
    import pathlib

    def fake_is_file(self):
        return str(self).startswith(sys.prefix)

    monkeypatch.setattr(pathlib.Path, "is_file", fake_is_file)
    expected = (Path(sys.prefix) / "share" / "pkgforge" / "scripts"
                / "install_helper.sh")
    assert _find_install_helper() == expected
    assert _find_install_helper().name == "install_helper.sh"


def test_find_helper_usr_share(qapp, monkeypatch):
    import pathlib

    def fake_is_file(self):
        return str(self).startswith("/usr/share/pkgforge")

    monkeypatch.setattr(pathlib.Path, "is_file", fake_is_file)
    assert _find_install_helper() == Path(
        "/usr/share/pkgforge/scripts/install_helper.sh")


def test_find_helper_fallback_first(qapp, monkeypatch):
    import pathlib
    monkeypatch.setattr(pathlib.Path, "is_file", lambda self: False)
    # Hicbir aday yoksa SISTEM yolu doner (polkit yalnizca orayi tanir).
    assert _find_install_helper() == Path(
        "/usr/share/pkgforge/scripts/install_helper.sh")


# ── _verify_installation (7 mutant): arguman yakalama ──────────
def test_verify_captures_pacman_args(qapp, monkeypatch):
    seen = {}

    def capture(cmd, timeout=None):
        seen["cmd"] = cmd
        seen["timeout"] = timeout
        return NS(returncode=0)

    monkeypatch.setattr(INS, "safe_run", capture)
    inst = _mk_installer(qapp)
    inst._pkg_name = "demo"
    assert inst._verify_installation() is True
    assert seen["cmd"] == ["/usr/bin/pacman", "-Qi", "demo"]
    assert seen["timeout"] == 10


def test_verify_nonzero_returns_false(qapp, monkeypatch):
    monkeypatch.setattr(INS, "safe_run",
                        lambda cmd, timeout=None: NS(returncode=2))
    inst = _mk_installer(qapp)
    inst._pkg_name = "demo"
    assert inst._verify_installation() is False


# ── _on_finished (14 mutant): kesin mesaj + ok + bos snap hint ─
def test_on_finished_cancelled_exact(qapp):
    inst = _mk_installer(qapp)
    got, _l = _spy(inst)
    inst._cancelled = True
    inst._on_finished(0, None)
    assert got[0] == (False, "Kurulum kullanıcı tarafından iptal edildi")


def test_on_finished_exit_codes_fail_flag(qapp):
    inst = _mk_installer(qapp)
    got, _l = _spy(inst)
    inst._pkg_name = "demo"
    inst._snapshot_name = ""
    inst._on_finished(126, None)
    assert got[-1] == (False, "Yetkilendirme reddedildi (Polkit)")
    inst._on_finished(127, None)
    assert got[-1] == (False, "pkexec komutu bulunamadı")
    inst._on_finished(9, None)
    assert got[-1] == (False, "Kurulum başarısız (kod: 9)")


def test_on_finished_success_no_snapshot_exact(qapp, monkeypatch):
    inst = _mk_installer(qapp)
    got, lines = _spy(inst)
    inst._pkg_name = "demo"
    inst._snapshot_name = ""
    monkeypatch.setattr(INS, "safe_run",
                        lambda cmd, timeout=None: NS(returncode=0))
    inst._on_finished(0, None)
    assert got[-1] == (True, "demo başarıyla kuruldu")
    assert "✓ demo başarıyla kuruldu/güncellendi" in lines



