"""Tur-25 — pipeline son dallari: iptal-kapisi ve baglanti-sokma korulari."""
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
    def __init__(self, disconnect_raises=False):
        self.fns = []
        self._dr = disconnect_raises

    def connect(self, fn):
        self.fns.append(fn)

    def disconnect(self, fn=None):
        if self._dr:
            raise TypeError("bagli degil")
        self.fns.remove(fn) if fn in self.fns else None

    def emit(self, *a):
        for fn in list(self.fns):
            fn(*a)


def _tools():
    return NS(missing_required=[], missing_optional=[], debtap="")


@pytest.fixture()
def ortem(qapp, monkeypatch, tmp_path):
    deb = tmp_path / "g.deb"
    deb.write_bytes(b"D")
    pkg = tmp_path / "cikti.pkg.tar.zst"
    pkg.write_bytes(b"P")
    mp = monkeypatch
    mp.setattr(PL, "discover_tools", lambda: _tools())
    mp.setattr(PL, "create_temp_dir", lambda: tmp_path / "tmpd")
    (tmp_path / "tmpd").mkdir()
    mp.setattr(PL, "validate_mime_type", lambda p, t: "application/x-deb")
    mp.setattr(PL, "validate_file_size", lambda *a, **k: None)
    mp.setattr(PL, "sha256_hash", lambda p: "ab" * 32)
    mp.setattr(PL, "verify_deb_signature",
               lambda p, t: NS(has_signature=False, detail="imza yok"))
    mp.setattr("i18n.load_setting", lambda k, d=False: False)
    mp.setattr(PL, "analyze_package", lambda p, t: NS(
        name="demo", version="1.0", arch="amd64", arch_mapped="x86_64",
        package_type="deb", file_list=[]))
    return pipe_obj(), deb, tmp_path, pkg


def pipe_obj():
    return ConversionPipeline()


def test_cancel_during_security_skips_malware(monkeypatch, ortem):
    pipe, deb, _tmp_path, _pkg = ortem

    def bomb_setler_cancel(p, t):
        pipe._cancelled = True          # guvenlik adimi sirasinda iptal

    monkeypatch.setattr("core.security.check_compression_bomb",
                        bomb_setler_cancel)
    monkeypatch.setattr(PL, "run_compatibility_checks",
                        lambda *a, **k: NS(overall=NS(value="pass"),
                                           checks=[]))
    pipe._decision_made = True
    pipe._decision_approved = True
    pipe._run_pipeline(deb)
    assert pipe._result.success is False       # akis malware oncesi dondu


def test_wait_decision_disconnect_type_error(qapp, monkeypatch):
    pipe = ConversionPipeline()
    sahte_sinyal = Sig(disconnect_raises=True)

    class HemenCikanLoop:
        cagri: ClassVar[int] = 0
        def __init__(self):
            pass
        def exec(self):
            HemenCikanLoop.cagri += 1
            if HemenCikanLoop.cagri >= 2:
                pipe._decision_made = True   # ikinci turda donguden cik
        def quit(self):
            pass

    monkeypatch.setattr(PL, "QEventLoop", HemenCikanLoop, raising=False)
    monkeypatch.setattr(pipe, "_decision_signal", sahte_sinyal,
                        raising=False)
    sonuc = pipe._wait_for_decision()
    assert sonuc is False                     # approved False


def test_convert_deb_finished_disconnect_type_error(ortem, monkeypatch, qapp):
    pipe, deb, tmp_path, pkg = ortem
    fin = Sig(disconnect_raises=True)         # disconnect TypeError firlatir

    def body(self):
        QTimer.singleShot(0, lambda: fin.emit(True, "tamam", pkg))

    class FakeConv:
        instances: ClassVar[list] = []

        def __init__(self, tools, parent=None):
            self.output_line = Sig()
            self.finished = fin
            FakeConv.instances.append(self)

        def convert(self, deb_path, output_dir):
            body(self)

    monkeypatch.setattr("core.native_deb_converter.NativeDebConverter",
                        FakeConv)
    pipe._convert_deb(deb, tmp_path)
    assert pipe._async_success is True and pipe._async_pkg_path == pkg