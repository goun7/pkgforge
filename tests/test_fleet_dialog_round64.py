"""Tur-64 — PyQt6 FleetDialog testleri (offscreen)."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication

import ui.fleet_dialog as FD
from ui.fleet_dialog import FleetDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def sync_bg(monkeypatch):
    def run(fn, on_done=None, on_error=None):
        try:
            result = fn()
            if on_done:
                on_done(result)
        except Exception as e:  # noqa: BLE001
            if on_error:
                on_error(str(e))

    monkeypatch.setattr(FD, "run_in_background", run)


FAKE = {
    "backends": {
        "webdav": {"configured": True, "available": True},
        "git": {"configured": False, "available": True},
        "rclone-s3": {"configured": False, "available": False},
    },
    "backend_names": ["webdav", "git", "rclone-s3"],
    "age_available": True,
    "profiles": ["default", "is"],
    "sync_configured": True,
    "history_count": 7,
    "policy_level": "STRICT",
}


def test_render_full(app, sync_bg, monkeypatch):
    import core.fleet as FL
    monkeypatch.setattr(FL, "get_fleet_status", lambda: FAKE)
    d = FleetDialog()
    summary = d._summary.text()
    detail = d._detail.text()
    assert "webdav" in summary and "git" in summary and "rclone-s3" in summary
    assert "STRICT" in detail
    assert "default, is" in detail
    assert "7" in detail
    d.deleteLater()


def test_render_error(app, sync_bg, monkeypatch):
    import core.fleet as FL

    def boom():
        raise RuntimeError("fleet patladi")

    monkeypatch.setattr(FL, "get_fleet_status", boom)
    d = FleetDialog()
    assert "fleet patladi" in d._summary.text()
    d.deleteLater()


def test_refresh_button(app, sync_bg, monkeypatch):
    import core.fleet as FL
    monkeypatch.setattr(FL, "get_fleet_status", lambda: FAKE)
    d = FleetDialog()
    assert d._refresh_btn is not None
    d._refresh_btn.click()
    assert "webdav" in d._summary.text()
    d.deleteLater()


# ── MainWindow fleet butonu ─────────────────────────────────────
import ui.main_window as MW
from config import ToolPaths


@pytest.fixture()
def win(app, monkeypatch):
    monkeypatch.setattr(MW, "discover_tools",
                        lambda: ToolPaths(debtap="/u/debtap", makepkg="/u/makepkg",
                                          pacman="/u/pacman", rpm2cpio="/u/rpm2cpio"))

    class FakePipeline:
        def __init__(self):
            pass

    monkeypatch.setattr(MW, "ConversionPipeline", FakePipeline)
    w = MW.MainWindow()
    yield w
    w.deleteLater()


def test_mainwindow_has_fleet_btn(win):
    assert hasattr(win, "_fleet_btn")


def test_show_fleet_opens_dialog(win, monkeypatch):
    called = []

    class FakeFleet:
        def __init__(self, parent=None):
            called.append("init")

        def exec(self):
            called.append("exec")

    monkeypatch.setattr(MW, "FleetDialog", FakeFleet)
    win._show_fleet()
    assert called == ["init", "exec"]

