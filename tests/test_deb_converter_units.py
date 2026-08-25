"""Coverage itmesi — core/deb_converter.py donusum sonuc dallari."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication

from core.deb_converter import DebConverter


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def _spy(conv):
    got = []
    lines = []
    conv.finished.connect(lambda ok, msg, p: got.append((ok, msg, p)))
    conv.output_line.connect(lambda s: lines.append(s))
    return got, lines


def _conv(qapp, debtap="/usr/bin/debtap"):
    tools = NS(debtap=debtap, bwrap="", pacman="/usr/bin/pacman")
    return DebConverter(tools)


def test_convert_without_debtap(qapp):
    conv = _conv(qapp, debtap="")
    got, _l = _spy(conv)
    conv.convert("x.deb", "out")
    assert got[0][0] is False and "debtap bulunamadı" in got[0][1]


def test_on_finished_cancelled(qapp):
    conv = _conv(qapp)
    got, _l = _spy(conv)
    conv._cancelled = True
    conv._on_finished(0, None)
    assert got[0][0] is False and "iptal" in got[0][1].lower()


def test_on_finished_nonzero(qapp):
    conv = _conv(qapp)
    got, _l = _spy(conv)
    conv._on_finished(3, None)
    assert got[0][0] is False and "hata kodu" in got[0][1]


def test_find_output_skips_sidecars(qapp, tmp_path):
    conv = _conv(qapp)
    conv._output_dir = tmp_path
    (tmp_path / "demo.pkg.tar.zst.sig").write_bytes(b"s")
    (tmp_path / "demo.pkg.tar.zst.provenance.json").write_text("{}")
    gercek = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    gercek.write_bytes(b"p")
    assert conv._find_output_package() == gercek


def test_on_finished_success_and_missing_pkg(qapp, tmp_path):
    conv = _conv(qapp)
    got, lines = _spy(conv)
    conv._output_dir = tmp_path
    (tmp_path / "cikti-1.0-1-x86_64.pkg.tar.zst").write_bytes(b"p")
    conv._on_finished(0, None)
    assert got[0][0] is True and got[0][2].name == "cikti-1.0-1-x86_64.pkg.tar.zst"
    assert any("Paket oluşturuldu" in s for s in lines)

    bos = tmp_path / "bos"
    bos.mkdir()
    conv2 = _conv(qapp)
    got2, _l2 = _spy(conv2)
    conv2._output_dir = bos
    conv2._on_finished(0, None)
    assert got2[0][0] is False and "bulunamadı" in got2[0][1]


def test_on_error_message_map(qapp):
    from PyQt6.QtCore import QProcess
    conv = _conv(qapp)
    got, _l = _spy(conv)
    cases = {
        QProcess.ProcessError.FailedToStart: "başlatılamadı",
        QProcess.ProcessError.Crashed: "sonlandı",
        QProcess.ProcessError.Timedout: "zaman aşımı",
        QProcess.ProcessError.UnknownError: "Bilinmeyen",
    }
    for err, needle in cases.items():
        conv._on_error(err)
        assert needle in got[-1][1], err
