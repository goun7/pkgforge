"""Coverage itmesi — core/deb_converter.py donusum sonuc dallari."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication, QProcess

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


# --- sahte QProcess ile kalan dallar -------------------------------------------

class _FakeProc:
    """QProcess yerine gecen minimal kayit araci."""

    class ProcessChannelMode:
        MergedChannels = 1

    class ProcessState:
        NotRunning = 0
        Running = 2

    class _Sig:
        def connect(self, *_):
            pass

    def __init__(self, parent=None):
        self.calls = []
        self._payload = b""
        self.state_value = 2
        self.readyReadStandardOutput = self._Sig()
        self.finished = self._Sig()
        self.errorOccurred = self._Sig()

    def setWorkingDirectory(self, d):
        self.calls.append(("cwd", d))

    def setProcessChannelMode(self, m):
        self.calls.append(("chan", m))

    def connect(self, *_):
        pass

    def start(self, prog, args):
        self.calls.append(("start", prog, list(args)))

    def state(self):
        return self.state_value

    def kill(self):
        self.calls.append(("kill",))

    def readAllStandardOutput(self):
        return NS(data=lambda: self._payload)


def test_convert_happy_path_starts_sandboxed_process(qapp, tmp_path, monkeypatch):
    deb = tmp_path / "demo.deb"
    deb.write_bytes(b"d")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr("core.deb_converter.QProcess", _FakeProc)
    fake_holder = {}
    orig_init = _FakeProc.__init__

    def _capture(self, parent=None):
        orig_init(self, parent)
        fake_holder["p"] = self
    _FakeProc.__init__ = _capture
    conv = _conv(qapp)
    _got, lines = _spy(conv)
    conv.convert(deb, out_dir)
    starts = [c for c in fake_holder["p"].calls if c[0] == "start"]
    assert starts and starts[0][1] == "/usr/bin/debtap"
    assert str(out_dir) in starts[0][2]
    assert any("▶ debtap" in s for s in lines)


def test_cancel_running_and_idle(qapp):
    conv = _conv(qapp)
    _got, lines = _spy(conv)
    proc = _FakeProc()
    conv._process = proc
    conv.cancel()
    assert proc.calls[-1][0] == "kill"
    assert any("iptal" in s for s in lines)

    idle = _FakeProc()
    # Gercek Qt sozlesmesi: state(), enum uyesi dondurur (int degil).
    idle.state_value = QProcess.ProcessState.NotRunning
    conv._process = idle
    conv.cancel()
    assert not any(c[0] == "kill" for c in idle.calls)


def test_on_output_emits_stripped_lines(qapp):
    conv = _conv(qapp)
    _got, lines = _spy(conv)
    proc = _FakeProc()
    proc._payload = b"  satir1\n\n satir2 \n"
    conv._process = proc
    conv._on_output()
    assert lines == ["satir1", "satir2"]


def test_on_output_without_process_noop(qapp):
    conv = _conv(qapp)
    conv._process = None
    conv._on_output()  # hata vermemeli