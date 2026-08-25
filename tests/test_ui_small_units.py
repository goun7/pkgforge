"""Coverage itmesi — ui/confirm_dialog.py ve ui/loading_indicator.py kalan dallari."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton

from ui.confirm_dialog import ConfirmDialog, confirm_action
from ui.loading_indicator import LoadingIndicator, SpinnerWidget


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# --- ConfirmDialog -------------------------------------------------------------

def test_danger_button_styling_branch(app):
    d = ConfirmDialog(title="t", message="m", confirm_text="Sil", danger=True)
    stil = next(b.styleSheet() for b in d.findChildren(QPushButton)
                if b.text() == "Sil")
    assert "background-color" in stil
    d.deleteLater()


def test_confirm_action_accept_and_reject(app, monkeypatch):
    monkeypatch.setattr(ConfirmDialog, "exec",
                        lambda self: QDialog.DialogCode.Accepted)
    assert confirm_action("t", "m") is True
    monkeypatch.setattr(ConfirmDialog, "exec",
                        lambda self: QDialog.DialogCode.Rejected)
    assert confirm_action("t", "m", confirm_text="Onayla") is False


def test_default_confirm_text_used(app):
    d = ConfirmDialog(title="t", message="m")
    metinler = [b.text() for b in d.findChildren(QPushButton)]
    assert len(metinler) == 2
    d.deleteLater()


# --- SpinnerWidget -------------------------------------------------------------

def test_spinner_rotate_and_lifecycle(app):
    s = SpinnerWidget(size=24)
    ilk = s._angle
    s._rotate()
    assert s._angle == (ilk + 10) % 360
    s.start()
    s.stop()
    assert not s.isVisibleTo(s.parent() or s)
    s.deleteLater()


def test_spinner_paint(app):
    s = SpinnerWidget(size=28)
    s.resize(28, 28)
    s.grab()  # paintEvent dali
    s.deleteLater()


# --- LoadingIndicator ----------------------------------------------------------

def test_loading_start_stop_update(app):
    li = LoadingIndicator()
    assert not li.isVisibleTo(li.parent() or li)  # kurulumda gizli
    li.start("isleniyor")
    assert li._label.text() == "isleniyor"
    li.update_text("%50")
    assert li._label.text() == "%50"
    li.stop()
    li.deleteLater()
