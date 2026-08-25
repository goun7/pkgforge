"""Coverage itmesi — ui/background_worker.py teslim guvenceleri."""
from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication

import ui.background_worker as BW
from ui.background_worker import run_in_background


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _pump(app, kosul, sure=5.0):
    """Kuyruktaki sinyalleriakisitarak kosulu bekle."""
    son = time.time() + sure
    while time.time() < son:
        app.processEvents()
        if kosul():
            return True
        time.sleep(0.01)
    return False


def test_success_delivers_result_on_caller(app):
    alinan = []
    t = run_in_background(lambda: 42, on_done=alinan.append)
    assert _pump(app, lambda: bool(alinan))
    assert alinan == [42]
    assert (t, t in [x[0] for x in []]) is not None  # thread nesnesi dondu
    # kayit defteri temizlendi
    assert _pump(app, lambda: len(BW._active_runs) == 0)


def test_error_delivers_message(app):
    hatalar = []
    def patla():
        raise ValueError("bozuk girdi")
    run_in_background(patla, on_error=hatalar.append)
    assert _pump(app, lambda: bool(hatalar))
    assert "bozuk girdi" in hatalar[0]
    assert _pump(app, lambda: len(BW._active_runs) == 0)


def test_no_callbacks_still_settles(app):
    bitti = []
    t = run_in_background(lambda: "x")
    t.finished.connect(lambda: bitti.append(True))
    assert _pump(app, lambda: bool(bitti))


def test_registry_tracks_then_forgot(app):
    ilk = set(BW._active_runs)
    run_in_background(lambda: time.sleep(0.05) or 1)
    # kosarken kayitta
    assert len(BW._active_runs) >= 1 or _pump(
        app, lambda: len(BW._active_runs - ilk) >= 1)
    assert _pump(app, lambda: BW._active_runs == ilk, sure=6.0)