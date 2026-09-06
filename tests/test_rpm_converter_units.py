"""Coverage itmesi - core/rpm_converter.py QProcess sahteleriyle tam akis."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import core.rpm_converter as RC
from core.rpm_converter import (
    RpmConverter,
    _escape_bash,
    _sanitize_pkgname,
    _sanitize_version,
)

Q = chr(39)

class Hook:
    def __init__(self):
        self.targets = []
    def connect(self, fn):
        self.targets.append(fn)
    def emit(self, *a):
        for t in list(self.targets):
            t(*a)

class FakeProc:
    class ProcessChannelMode:
        MergedChannels = 3
    class ProcessError:
        FailedToStart = 0
        Crashed = 1
        Timedout = 2
        UnknownError = 3
    def __init__(self):
        self.readyReadStandardOutput = Hook()
        self.finished = Hook()
        self.errorOccurred = Hook()
        self.killed = False
        self.started = None
    def setWorkingDirectory(self, d): pass
    def setProcessChannelMode(self, m): pass
    def setProcessEnvironment(self, env): pass
    def start(self, prog, args): self.started = (prog, tuple(args))
    def state(self): return 2 if self.started else 0
    def kill(self): self.killed = True
    def readAllStandardOutput(self): return NS(data=lambda: b"satir1\nsatir2\n")

class Factory:
    ProcessChannelMode = NS(MergedChannels=3)
    ProcessError = NS(FailedToStart=0, Crashed=1, Timedout=2, UnknownError=3)
    ProcessState = NS(NotRunning=0)

    def __init__(self): self.procs = []
    def __call__(self, parent=None):
        p = FakeProc()
        self.procs.append(p)
        return p

def _tools(**over):
    base = {"rpm2cpio": "/usr/bin/rpm2cpio", "bsdtar": "/usr/bin/bsdtar",
            "makepkg": "/usr/bin/makepkg", "bwrap": "", "pkexec": "", "pacman": ""}
    base.update(over)
    return NS(**base)

def _meta():
    return NS(name="araclar", version="2.5-3.fc40", depends=["openssl"], arch_mapped="x86_64", description="aciklama", url="https://x")

def _converter(monkeypatch, **tool_over):
    fac = Factory()
    monkeypatch.setattr(RC, "QProcess", fac)
    monkeypatch.setattr(RC, "resolve_runtime_dependencies", lambda d, t: [])
    monkeypatch.setattr(RC, "check_symlink_attacks", lambda p: [])
    monkeypatch.setattr(RC, "check_dangerous_files", lambda p: ([], []))
    conv = RpmConverter(_tools(**tool_over))
    lines = []
    results = []
    conv.output_line.connect(lines.append)
    conv.finished.connect(lambda ok, m, p: results.append((ok, m, p)))
    return conv, fac, lines, results

def test_missing_tool_guards():
    for missing in ("makepkg", "bsdtar", "rpm2cpio"):
        c = RpmConverter(_tools())
        setattr(c._tools, missing, "")
        got = []
        c.finished.connect(lambda ok, m, p, got=got: got.append(m))
        c.convert(Path("/tmp/a.rpm"), Path("/tmp/w"), _meta())
        assert got and missing in got[0]

def test_cancel_and_output_lines(monkeypatch, tmp_path):
    conv, fac, lines, results = _converter(monkeypatch)
    rpm = tmp_path / "a.rpm"
    rpm.write_bytes(b"x")
    conv.convert(rpm, tmp_path, _meta())
    p1 = fac.procs[0]
    assert p1.started[0] == "/bin/bash" and "|" in p1.started[1][1]
    p1.readyReadStandardOutput.emit()
    assert lines[-2:] == ["satir1", "satir2"]
    conv.cancel()
    assert p1.killed is True
    p1.finished.emit(0, None)
    assert results and results[0][0] is False and "ptal" in results[0][1]

def test_extract_failure(monkeypatch, tmp_path):
    conv, fac, _lines, results = _converter(monkeypatch)
    conv.convert(tmp_path / "a.rpm", tmp_path, _meta())
    fac.procs[0].finished.emit(3, None)
    assert results[0][0] is False and "kod: 3" in results[0][1]

def test_security_rejections(monkeypatch, tmp_path):
    conv, fac, _lines, results = _converter(monkeypatch)
    monkeypatch.setattr(RC, "check_symlink_attacks", lambda p: ["../evil"])
    conv.convert(tmp_path / "a.rpm", tmp_path, _meta())
    fac.procs[0].finished.emit(0, None)
    assert results[0][0] is False and "sembolik" in results[0][1]

    conv2, fac2, l2, res2 = _converter(monkeypatch)
    monkeypatch.setattr(RC, "check_symlink_attacks", lambda p: [])
    monkeypatch.setattr(RC, "check_dangerous_files", lambda p: (["setuid"], ["uyari"]))
    conv2.convert(tmp_path / "b.rpm", tmp_path / "w2", _meta())
    fac2.procs[0].finished.emit(0, None)
    assert res2[0][0] is False and "setuid" in res2[0][1]
    assert any("uyari" in x for x in l2)

def test_happy_build(monkeypatch, tmp_path):
    conv, fac, _lines, results = _converter(monkeypatch)
    monkeypatch.setattr("core.security.build_sandbox_cmd", lambda cmd, d, t: (cmd[0], tuple(cmd[1:])))
    conv.convert(tmp_path / "c.rpm", tmp_path, _meta())
    fac.procs[0].finished.emit(0, None)
    pkgbuild = tmp_path / "build" / "PKGBUILD"
    text = pkgbuild.read_text()
    assert ("pkgname=" + Q + "araclar" + Q) in text
    assert "depends=()" in text
    pkgout = tmp_path / "build" / "pkgout"
    out_pkg = pkgout / "araclar-2.5-1-x86_64.pkg.tar.zst"
    out_pkg.write_bytes(b"P")
    assert len(fac.procs) == 2 and fac.procs[1].started[0] == "/usr/bin/makepkg"
    fac.procs[1].finished.emit(0, None)
    # finalize: urun cikis kokune tasinir, src/ + pkg/ temizlenir
    assert results[-1][0] is True
    assert results[-1][2] == tmp_path / "araclar-2.5-1-x86_64.pkg.tar.zst"
    assert not (tmp_path / "build" / "src").exists()
    assert not out_pkg.exists()

def test_makepkg_fail_and_missing_output(monkeypatch, tmp_path):
    conv, fac, _lines, results = _converter(monkeypatch)
    monkeypatch.setattr("core.security.build_sandbox_cmd", lambda cmd, d, t: (cmd[0], tuple(cmd[1:])))
    conv.convert(tmp_path / "d.rpm", tmp_path, _meta())
    fac.procs[0].finished.emit(0, None)
    fac.procs[1].finished.emit(9, None)
    assert results[-1][0] is False and "kod: 9" in results[-1][1]

    conv2, fac2, _l2, res2 = _converter(monkeypatch)
    monkeypatch.setattr("core.security.build_sandbox_cmd", lambda cmd, d, t: (cmd[0], tuple(cmd[1:])))
    conv2.convert(tmp_path / "e.rpm", tmp_path / "we", _meta())
    fac2.procs[0].finished.emit(0, None)
    fac2.procs[1].finished.emit(0, None)
    assert res2[-1][0] is False and "bulunamad" in res2[-1][1]

def test_error_map_and_sanitizers():
    conv = RpmConverter(_tools())
    got = []
    conv.finished.connect(lambda ok, m, p: got.append((ok, m)))
    pe = RC.QProcess.ProcessError
    conv._on_error(pe.FailedToStart)
    conv._on_error(pe.Crashed)
    conv._on_error(pe.UnknownError)
    assert "başlatılamadı" in got[0][1] and "çöktü" in got[1][1] and "Bilinmeyen" in got[2][1]
    import re as _re
    s = _sanitize_pkgname("Gnome Araçlar!")
    assert s.startswith("gnome-ara") and _re.fullmatch(r"[a-z0-9+@._-]*", s)
    v = _sanitize_version("1.2~rc1")
    assert v.startswith("1.2")
    e = _escape_bash("it" + Q + "s; rm")
    assert e.count(chr(92)) >= 1