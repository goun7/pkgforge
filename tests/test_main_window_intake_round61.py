"""Tur-61 — MainWindow universal intake: belirsiz tarball secimi ve forced_type."""
from __future__ import annotations

import io
import os
import tarfile
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication

import ui.main_window as MW
from config import ToolPaths


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakePipeline:
    def __init__(self):
        self.step_changed = NS(connect=lambda f: None)
        self.progress = NS(connect=lambda f: None)
        self.log_message = NS(connect=lambda f: None)
        self.compatibility_ready = NS(connect=lambda f: None)
        self.finished = NS(connect=lambda f: None)
        self.staged = None
        self.staged_forced = None

    def moveToThread(self, t):
        pass

    def stage(self, p, forced=None):
        self.staged = p
        self.staged_forced = forced

    def run_staged(self):
        pass

    def cancel(self):
        pass


class FakeMsgBox:
    ButtonRole = NS(AcceptRole=0, RejectRole=1)
    click_index = 0

    def __init__(self, parent=None):
        self._buttons = []
        self._clicked = None

    def setWindowTitle(self, t):
        pass

    def setText(self, t):
        pass

    def addButton(self, text, role):
        b = object()
        self._buttons.append(b)
        return b

    def exec(self):
        if self._buttons:
            self._clicked = self._buttons[FakeMsgBox.click_index]

    def clickedButton(self):
        return self._clicked


class FakeThread:
    def __init__(self):
        self.started = NS(connect=lambda f: None)

    def start(self):
        pass

    def quit(self):
        pass

    def wait(self, ms=0):
        pass


@pytest.fixture()
def win(app, monkeypatch):
    monkeypatch.setattr(MW, "discover_tools",
                        lambda: ToolPaths(debtap="/u/debtap", makepkg="/u/makepkg",
                                          pacman="/u/pacman", rpm2cpio="/u/rpm2cpio"))
    monkeypatch.setattr(MW, "ConversionPipeline", FakePipeline)
    monkeypatch.setattr(MW, "QThread", FakeThread)
    w = MW.MainWindow()
    yield w
    w.deleteLater()


def _ambig_tarball(tmp_path: Path) -> Path:
    f = tmp_path / "belirsiz.tar.gz"
    with tarfile.open(f, "w:gz") as tf:
        for name in ("Cargo.toml", "usr/bin/app"):
            info = tarfile.TarInfo(name=name)
            info.size = 1
            tf.addfile(info, io.BytesIO(b"x"))
    return f


# ── _resolve_ambiguous_type ─────────────────────────────────────
def test_resolve_ambig_source(win, monkeypatch, tmp_path):
    monkeypatch.setattr(MW, "QMessageBox", FakeMsgBox)
    FakeMsgBox.click_index = 0
    assert win._resolve_ambiguous_type(tmp_path / "x.tar.gz") == "source_tarball"


def test_resolve_ambig_binary(win, monkeypatch, tmp_path):
    monkeypatch.setattr(MW, "QMessageBox", FakeMsgBox)
    FakeMsgBox.click_index = 1
    assert win._resolve_ambiguous_type(tmp_path / "x.tar.gz") == "binary_tarball"


def test_resolve_ambig_cancel(win, monkeypatch, tmp_path):
    monkeypatch.setattr(MW, "QMessageBox", FakeMsgBox)
    FakeMsgBox.click_index = 2
    assert win._resolve_ambiguous_type(tmp_path / "x.tar.gz") is None


# ── _on_files_dropped ───────────────────────────────────────────
def test_drop_plain_deb_no_dialog(win, tmp_path):
    deb = tmp_path / "p.deb"
    deb.write_bytes(b"x")
    win._on_files_dropped([deb])
    assert win._queue.total == 1
    assert win._forced_types == {}


def test_drop_ambig_source_sets_forced(win, monkeypatch, tmp_path):
    monkeypatch.setattr(MW, "QMessageBox", FakeMsgBox)
    FakeMsgBox.click_index = 0
    f = _ambig_tarball(tmp_path)
    win._on_files_dropped([f])
    assert win._queue.total == 1
    assert win._forced_types[str(f)] == "source_tarball"


def test_drop_ambig_cancel_skips(win, monkeypatch, tmp_path):
    monkeypatch.setattr(MW, "QMessageBox", FakeMsgBox)
    FakeMsgBox.click_index = 2
    f = _ambig_tarball(tmp_path)
    win._on_files_dropped([f])
    assert win._queue.total == 0
    assert win._forced_types == {}
