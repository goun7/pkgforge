"""Coverage itmesi — core/distrobox_fallback.py faz zinciri."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication

import core.distrobox_fallback as DB
from core.distrobox_fallback import DistroboxFallback


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class Hook:
    def __init__(self):
        self.fns = []

    def connect(self, fn):
        self.fns.append(fn)


class FakeQProcess:
    ProcessChannelMode = NS(MergedChannels=3)

    def __init__(self, parent=None):
        self.started = []
        self.readyReadStandardOutput = Hook()
        self.finished = Hook()
        self.errorOccurred = Hook()
        DistroboxFallbackUnit.last_process = self

    def setProcessChannelMode(self, mode):
        pass

    def start(self, prog, args):
        self.started.append((prog, args))


DistroboxFallbackUnit = type("Holder", (), {"last_process": None})


def _tools(distrobox="/usr/bin/distrobox"):
    return NS(distrobox=distrobox, has_distrobox=bool(distrobox))


def _spy(fb):
    got = []
    fb.finished.connect(lambda ok, msg: got.append((ok, msg)))
    return got


def test_is_available():
    assert DistroboxFallback.is_available(_tools()) is True
    assert DistroboxFallback.is_available(_tools("")) is False


def test_install_without_distrobox(qapp):
    fb = DistroboxFallback(_tools(""))
    got = _spy(fb)
    fb.install_in_container(Path("/tmp/x.deb"), "x")
    assert got == [(False, "distrobox bulunamadı")]


def test_container_name_sanitized(qapp):
    fb = DistroboxFallback(_tools())
    _spy(fb)
    fb.install_in_container(Path("/tmp/x.deb"), "../../evil;rm -rf")
    name = fb._container_name
    assert name.startswith("pkgforge-")
    assert "/" not in name and ";" not in name and " " not in name


def test_create_failure_and_success_chain(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(DB, "QProcess", FakeQProcess)
    pkg = tmp_path / "ara.deb"
    pkg.write_bytes(b"x")
    fb = DistroboxFallback(_tools())
    got = _spy(fb)

    fb._pkg_name = "ara"
    fb._on_create_finished(5, None)
    assert got[0][0] is False and "kod: 5" in got[0][1]

    fb.install_in_container(pkg, "ara", "deb")
    proc = DistroboxFallbackUnit.last_process
    assert proc.started[0][0] == "/usr/bin/distrobox"
    assert proc.started[0][1][0] == "create"

    fb._on_create_finished(0, None)
    assert fb._phase == "install"
    proc = DistroboxFallbackUnit.last_process
    prog, args = proc.started[-1]
    assert prog == "/bin/bash"
    assert "dpkg -i" in args[1] and "apt-get" in args[1]


def test_install_and_export_chain(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(DB, "QProcess", FakeQProcess)
    pkg = tmp_path / "ara.rpm"
    pkg.write_bytes(b"x")
    fb = DistroboxFallback(_tools())
    _spy(fb)
    fb.install_in_container(pkg, "arac", "rpm")
    proc = DistroboxFallbackUnit.last_process

    fb._on_create_finished(0, None)   # -> install (rpm yolu)
    proc = DistroboxFallbackUnit.last_process
    _prog, args = proc.started[-1]
    assert "rpm -i" in args[1] and "dnf install -y" in args[1]

    fb._on_install_finished(0, None)  # -> export
    assert fb._phase == "export"
    proc = DistroboxFallbackUnit.last_process
    _prog2, args2 = proc.started[-1]
    assert args2[0] == "enter" and "distrobox-export" in args2
