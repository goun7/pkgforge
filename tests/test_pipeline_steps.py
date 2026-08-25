"""Coverage itmesi — pipeline adim zinciri: kurulum kapisi ve donusturuculer."""
from __future__ import annotations

from types import SimpleNamespace as NS
from typing import ClassVar

import pytest
from PyQt6.QtCore import QCoreApplication, QTimer

import core.pipeline as PL
from core.pipeline import ConversionPipeline


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class Sig:
    def __init__(self):
        self.fns = []

    def connect(self, fn):
        self.fns.append(fn)

    def disconnect(self, fn=None):
        pass

    def emit(self, *a):
        for fn in list(self.fns):
            fn(*a)


def _tools(**kw):
    base = {"missing_required": [], "missing_optional": [], "debtap": ""}
    base.update(kw)
    return NS(**base)


@pytest.fixture()
def pipe(qapp, monkeypatch):
    monkeypatch.setattr(PL, "discover_tools", lambda: _tools())
    return ConversionPipeline()


def test_do_install_dry_run(pipe, monkeypatch, tmp_path):
    monkeypatch.setattr("i18n.load_setting", lambda k, d=False: True)
    steps = []
    pipe._set_step = lambda s, st: steps.append((s, st))
    pipe._do_install(tmp_path / "p.pkg.tar.zst", "demo")
    assert pipe._result.success is True
    assert "dry-run" in pipe._result.message


def _make_fake_converter(sig_finished, convert_body=None):
    class FakeConv:
        instances: ClassVar[list] = []

        def __init__(self, tools, parent=None):
            self.output_line = Sig()
            self.finished = sig_finished
            FakeConv.instances.append(self)

        def convert(self, deb_path, output_dir):
            if convert_body:
                convert_body(self)
    return FakeConv


def test_do_install_real_success(pipe, monkeypatch, tmp_path, qapp):
    monkeypatch.setattr("i18n.load_setting", lambda k, d=False: False)
    fin = Sig()

    class FakeInstaller:
        last = None

        def __init__(self, tools, parent=None):
            self.output_line = Sig()
            self.finished = fin
            FakeInstaller.last = self

        def install(self, pkg, name):
            QTimer.singleShot(0, lambda: fin.emit(True, "kuruldu"))
    monkeypatch.setattr("core.installer.Installer", FakeInstaller)
    steps = []
    pipe._set_step = lambda s, st: steps.append((s, st))
    pipe._do_install(tmp_path / "p.pkg.tar.zst", "demo")
    assert pipe._result.success is True and "başarıyla kuruldu" in pipe._result.message


def test_do_install_failure(pipe, monkeypatch, tmp_path):
    monkeypatch.setattr("i18n.load_setting", lambda k, d=False: False)
    fin = Sig()

    class FakeInstaller:
        def __init__(self, tools, parent=None):
            self.output_line = Sig()
            self.finished = fin

        def install(self, pkg, name):
            QTimer.singleShot(0, lambda: fin.emit(False, "pkexec reddi"))
    monkeypatch.setattr("core.installer.Installer", FakeInstaller)
    pipe._do_install(tmp_path / "p.pkg.tar.zst", "demo")
    assert pipe._result.success is False and "pkexec reddi" in pipe._result.message


def test_convert_deb_native_success(pipe, monkeypatch, tmp_path):
    fin = Sig()
    pkg = tmp_path / "cikti.pkg.tar.zst"

    def body(self):
        QTimer.singleShot(0, lambda: fin.emit(True, "tamam", pkg))
    fake = _make_fake_converter(fin, body)
    monkeypatch.setattr("core.native_deb_converter.NativeDebConverter", fake)
    pipe._convert_deb(tmp_path / "x.deb", tmp_path)
    assert pipe._async_success is True and pipe._async_pkg_path == pkg
    assert pipe._deb_converter is not None


def test_convert_deb_debtap_fallback(pipe, monkeypatch, tmp_path):
    native_fin = Sig()
    fb_fin = Sig()
    fb_pkg = tmp_path / "fb.pkg.tar.zst"

    def native_body(self):
        QTimer.singleShot(0, lambda: native_fin.emit(False, "kirik", None))
    fake_native = _make_fake_converter(native_fin, native_body)

    def fb_body(self):
        QTimer.singleShot(0, lambda: fb_fin.emit(True, "debtap tamam", fb_pkg))
    fake_fb = _make_fake_converter(fb_fin, fb_body)

    monkeypatch.setattr("core.native_deb_converter.NativeDebConverter", fake_native)
    monkeypatch.setattr("core.deb_converter.DebConverter", fake_fb)
    pipe._tools = _tools(debtap="/usr/bin/debtap")
    pipe._convert_deb(tmp_path / "x.deb", tmp_path)
    assert pipe._async_success is True and pipe._async_pkg_path == fb_pkg
