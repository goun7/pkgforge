"""Coverage itmesi — ui/step_progress.py durum/nokta/baglaci dallari."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication

from ui.step_progress import StepConnector, StepDot, StepProgress


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _render(widget, app):
    widget.resize(60, 60)
    widget.grab()  # paintEvent'i zorla calistirir


# --- StepDot -------------------------------------------------------------------

def test_dot_status_transitions(app):
    d = StepDot()
    assert d.status == "pending"
    for st in ("running", "done", "warning", "error", "pending", "skipped"):
        d.status = st
        assert d.status == st
    d.deleteLater()


def test_dot_pulse_tick_and_paint_all_statuses(app):
    d = StepDot()
    d.status = "running"
    d._pulse_timer.stop()
    for _ in range(3):
        d._pulse_tick()
    assert 0.0 <= d._pulse_opacity <= 0.6
    for st in ("pending", "running", "done", "warning", "error", "skipped", "bilinmeyen"):
        d._status = st
        _render(d, app)  # her boyama dalı
    d.deleteLater()


# --- StepConnector -------------------------------------------------------------

def test_connector_active_paints_both_ways(app):
    c = StepConnector()
    assert c.active is False
    _render(c, app)
    c.active = True
    assert c.active is True
    _render(c, app)
    c.deleteLater()


# --- StepProgress --------------------------------------------------------------

@pytest.fixture()
def sp(app):
    w = StepProgress()
    yield w
    w.deleteLater()


def test_setup_builds_five_steps(sp):
    assert len(sp._steps) == 6 and len(sp._connectors) == 5


def test_set_step_status_unknown_index_noop(sp):
    sp.set_step_status(99, "done")  # cokmemeli
    sp.set_step_status(-1, "error")


def test_set_step_status_running_marks_connector(sp):
    sp.set_step_status(2, "running")
    dot, label = sp._steps[2]
    assert dot.status == "running"
    assert label.objectName() == "stepLabelActive"
    # onundeki baglac aktif degil; arkadakiler aktif (6 adim, 5 baglac)
    assert [c.active for c in sp._connectors] == [True, True, False, False, False]


def test_set_step_status_done_extends_connector(sp):
    sp.set_step_status(1, "done")
    assert [c.active for c in sp._connectors] == [True, True, False, False, False]
    sp.set_step_status(1, "pending")
    assert [c.active for c in sp._connectors] == [True, False, False, False, False]


def test_set_progress_clamps(sp):
    sp.set_progress(150)
    assert sp._progress_bar.value() == 100
    sp.set_progress(-5)
    assert sp._progress_bar.value() == 0
    sp.set_progress(42)
    assert sp._progress_bar.value() == 42


def test_reset_restores_initial(sp):
    sp.set_step_status(0, "done")
    sp.set_step_status(4, "error")
    sp.set_progress(88)
    sp.reset()
    assert all(sp._steps[i][0].status == "pending" for i in sp._steps)
    assert all(c.active is False for c in sp._connectors)
    assert sp._progress_bar.value() == 0


def test_retranslate_rewrites_labels(sp):
    before = {i: sp._steps[i][1].text() for i in sp._steps}
    sp.retranslate()
    after = {i: sp._steps[i][1].text() for i in sp._steps}
    assert before == after and all(after.values())

def test_analysis_dot_and_connector_turn_green(sp):
    """Task t3 regression: ANALYSIS (PipelineStep=2) done must light step 2 dot + connector."""
    from core.pipeline import PipelineStep
    sp.reset()
    sp.set_step_status(int(PipelineStep.ANALYSIS), "done")  # ui index 2 (Paket Analizi)
    assert sp._steps[2][0].status == "done"
    # connectors: 0->1-> before and at step 2
    assert sp._connectors[2].active is True
    assert sp._connectors[1].active is True
    assert sp._connectors[3].active is False


def test_malware_skipped_renders_like_done(sp):
    """MALWARE_SCAN skipped is shown as faded-green tick and its connector activates."""
    from core.pipeline import PipelineStep
    sp.reset()
    sp.set_step_status(int(PipelineStep.MALWARE_SCAN), "skipped")  # ui index 1
    assert sp._steps[1][0].status == "skipped"
    # skipped draws same tick (paint branch shared with done) and active connector
    assert sp._connectors[1].active is True


def test_full_pipeline_sequence_maps_correctly(sp):
    """Every pipeline step lights the correct UI dot (6 -> 6 direct mapping)."""
    from core.pipeline import PipelineStep
    sp.reset()
    # SECURITY done -> dot 0
    sp.set_step_status(int(PipelineStep.SECURITY), "done")
    assert sp._steps[0][0].status == "done"
    # MALWARE done -> dot 1
    sp.set_step_status(int(PipelineStep.MALWARE_SCAN), "done")
    assert sp._steps[1][0].status == "done"
    # ANALYSIS done -> dot 2
    sp.set_step_status(int(PipelineStep.ANALYSIS), "done")
    assert sp._steps[2][0].status == "done"
    # CONVERSION error -> dot 3 error
    sp.set_step_status(int(PipelineStep.CONVERSION), "error")
    assert sp._steps[3][0].status == "error"
    # COMPATIBILITY warning -> dot 4 warning
    sp.set_step_status(int(PipelineStep.COMPATIBILITY), "warning")
    assert sp._steps[4][0].status == "warning"
    # INSTALL done -> dot 5
    sp.set_step_status(int(PipelineStep.INSTALL), "done")
    assert sp._steps[5][0].status == "done"

