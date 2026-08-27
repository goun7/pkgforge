"""Tur-62 — PyQt6 Feature Tezgahi (ToolsDialog + MainWindow tools butonu)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication, QFileDialog

import ui.tools_dialog as TD
from ui.tools_dialog import ToolsDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def td(app):
    d = ToolsDialog()
    yield d
    d.deleteLater()


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

    monkeypatch.setattr(TD, "run_in_background", run)


def test_three_tabs(td):
    assert td._tabs.count() == 3


# ── RPM -> DEB ──────────────────────────────────────────────────
def test_rpm_missing_file(td, sync_bg):
    td._rpm_path.setText("")
    td._run_rpm_to_deb()
    assert "❌" in td._rpm_result.text()


def test_rpm_convert_success(td, sync_bg, monkeypatch, tmp_path):
    rpm = tmp_path / "p.rpm"
    rpm.write_bytes(b"x")
    td._rpm_path.setText(str(rpm))
    import core.rpm_to_deb_converter as R2D
    monkeypatch.setattr(R2D, "is_rpm_to_deb_available", lambda: True)
    monkeypatch.setattr(R2D, "rpm_to_deb",
                        lambda p, o: (True, "donustu", tmp_path / "p.deb"))
    td._run_rpm_to_deb()
    assert "donustu" in td._rpm_result.text()
    assert "p.deb" in td._rpm_result.text()
    assert td._rpm_btn.isEnabled()


def test_rpm_tools_missing(td, sync_bg, monkeypatch, tmp_path):
    rpm = tmp_path / "p.rpm"
    rpm.write_bytes(b"x")
    td._rpm_path.setText(str(rpm))
    import core.rpm_to_deb_converter as R2D
    monkeypatch.setattr(R2D, "is_rpm_to_deb_available", lambda: False)
    td._run_rpm_to_deb()
    assert "❌" in td._rpm_result.text()


def test_rpm_error_path(td, sync_bg, monkeypatch, tmp_path):
    rpm = tmp_path / "p.rpm"
    rpm.write_bytes(b"x")
    td._rpm_path.setText(str(rpm))
    import core.rpm_to_deb_converter as R2D
    monkeypatch.setattr(R2D, "is_rpm_to_deb_available", lambda: True)

    def boom(p, o):
        raise RuntimeError("patladi")

    monkeypatch.setattr(R2D, "rpm_to_deb", boom)
    td._run_rpm_to_deb()
    assert "patladi" in td._rpm_result.text()


def test_pick_rpm(td, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("/x/p.rpm", "")))
    td._pick_rpm()
    assert td._rpm_path.text() == "/x/p.rpm"


def test_pick_rpm_empty(td, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    td._rpm_path.setText("onceki")
    td._pick_rpm()
    assert td._rpm_path.text() == "onceki"


# ── ABI Check ───────────────────────────────────────────────────
def test_abi_missing_file(td, sync_bg):
    td._abi_path.setText("")
    td._run_abi_check()
    assert "❌" in td._abi_result.toPlainText()


def test_abi_success(td, sync_bg, monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    td._abi_path.setText(str(pkg))
    import core.abi_scanner as ABI
    report = ABI.ABIScanReport(binary_count=1, checked_symbols=5)
    monkeypatch.setattr(ABI, "check_abi_compatibility", lambda p: report)
    td._run_abi_check()
    assert "ABI" in td._abi_result.toPlainText()
    assert td._abi_btn.isEnabled()


def test_abi_error(td, sync_bg, monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    td._abi_path.setText(str(pkg))
    import core.abi_scanner as ABI

    def boom(p):
        raise RuntimeError("abi patladi")

    monkeypatch.setattr(ABI, "check_abi_compatibility", boom)
    td._run_abi_check()
    assert "abi patladi" in td._abi_result.toPlainText()


def test_pick_abi(td, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("/x/p.pkg.tar.zst", "")))
    td._pick_abi()
    assert td._abi_path.text() == "/x/p.pkg.tar.zst"


# ── Audit ───────────────────────────────────────────────────────
def _history_rec(**kw):
    from core.history_db import HistoryRecord
    base = {"id": 1, "timestamp": "2026-08-27", "package_name": "p",
            "original_file": "p.deb", "package_type": "deb", "sha256": "a",
            "status": "installed", "output_pkg": "", "details": ""}
    base.update(kw)
    return HistoryRecord(**base)


def test_audit_success(td, sync_bg, monkeypatch):
    import core.history_db as HD

    class FakeDB:
        def get_history(self, limit=100):
            return [_history_rec()]

    monkeypatch.setattr(HD, "HistoryDB", FakeDB)
    td._run_audit()
    assert "1" in td._audit_summary.text()
    assert "installed" in td._audit_detail.toPlainText()


def test_audit_error(td, sync_bg, monkeypatch):
    import core.history_db as HD

    class FakeDB:
        def get_history(self, limit=100):
            raise RuntimeError("db bozuk")

    monkeypatch.setattr(HD, "HistoryDB", FakeDB)
    td._run_audit()
    assert "db bozuk" in td._audit_detail.toPlainText()

# ── MainWindow tools butonu ─────────────────────────────────────
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


def test_mainwindow_has_tools_btn(win):
    assert hasattr(win, "_tools_btn")


def test_show_tools_opens_dialog(win, monkeypatch):
    called = []

    class FakeTools:
        def __init__(self, parent=None):
            called.append("init")

        def exec(self):
            called.append("exec")

    monkeypatch.setattr(MW, "ToolsDialog", FakeTools)
    win._show_tools()
    assert called == ["init", "exec"]

