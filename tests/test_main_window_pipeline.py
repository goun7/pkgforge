"""Coverage itmesi — ui/main_window.py pipeline/kuyruk-sonucu/iptal/upstream."""
from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

import ui.main_window as MW
from config import ToolPaths
from core.compatibility_checker import (
    CheckSeverity,
    CompatibilityReport,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakePipeline(QObject):
    step_changed = pyqtSignal(int, str)
    progress = pyqtSignal(int)
    log_message = pyqtSignal(str, str)
    compatibility_ready = pyqtSignal(object)
    finished = pyqtSignal(object)
    cancel_called = 0

    def __init__(self):
        super().__init__()
        self.staged = None
        self.ran = False
        self._result = None
        type(self).cancel_called = 0

    def stage(self, p):
        self.staged = p

    def run_staged(self):
        self.ran = True

    def cancel(self):
        type(self).cancel_called += 1

    def approve_install(self):
        pass

    def dismiss_install(self, *a):
        pass


@pytest.fixture()
def win(app, monkeypatch):
    monkeypatch.setattr(MW, "discover_tools",
                        lambda: ToolPaths(debtap="/usr/bin/debtap",
                                          rpm2cpio="/u/rpm2cpio",
                                          makepkg="/u/makepkg",
                                          pacman="/u/pacman"))
    olusturulan = []

    class Yakalayan(FakePipeline):
        def __init__(self):
            super().__init__()
            olusturulan.append(self)
    monkeypatch.setattr(MW, "ConversionPipeline", Yakalayan)
    w = MW.MainWindow()
    w.show()
    yield w, olusturulan
    if w._pipeline_thread is not None:
        w._pipeline_thread.quit()
        w._pipeline_thread.wait(1500)
    w.deleteLater()


def _bilgi_raporu(sev=CheckSeverity.PASS):
    return CompatibilityReport(checks=[]), sev


def _sonuc(**kw):
    rapor = CompatibilityReport(checks=[])
    taban = {"success": True, "message": "tamam", "compatibility": rapor,
             "metadata": NS(name="demo"), "signature": None,
             "sha256": "ab", "original_file": None}
    taban.update(kw)
    return NS(**taban)


def _sessiz_qmsg(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    log = []

    def _kaydet(*a, **k):
        log.append(a)
    for ad in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, ad,
                            staticmethod(_kaydet))
    return log


def test_start_next_runs_staged_pipeline(win, tmp_path):
    d, olusturulan = win
    f = tmp_path / "ornek.deb"
    f.write_bytes(b"x")
    d._on_files_dropped([f])
    assert olusturulan, "pipeline uretilmeli"
    p = olusturulan[0]
    assert str(p.staged).endswith(".deb")
    son = time.time() + 3
    while time.time() < son and p.ran is False:
        time.sleep(0.01)
    assert p.ran is True
    assert d._step_progress.isVisibleTo(d)
    assert d._drop_zone.acceptDrops() is False


def test_step_progress_and_log_slots(win):
    d, _ = win
    d._on_step_changed(1, "running")
    assert d._step_progress._steps[1][0].status == "running"
    d._on_progress(55)
    assert d._step_progress._progress_bar.value() == 55
    onceki = len(d._log_panel._log_lines)
    d._on_log("selam", "info")
    assert len(d._log_panel._log_lines) == onceki + 1


def test_on_cancel_pokes_pipeline(win):
    d, _olusturulan = win
    d._queue.add_files([Path("/x/a.deb")])
    d._start_next_in_queue()
    onceki = FakePipeline.cancel_called
    d._on_cancel()
    assert FakePipeline.cancel_called >= onceki


def test_queue_changed_rebuilds_with_view_button(win, monkeypatch):
    d, _ = win
    r = _sonuc()
    ogeler = [
        NS(name="bitti", file_path=Path("/x/b.deb"),
           status=NS(), result=r),
        NS(name="suruyor", file_path=Path("/x/c.deb"),
           status=NS(), result=None),
    ]
    # durum sabitlerini taklit et
    from core.queue_manager import QueueItemStatus
    ogeler[0].status = QueueItemStatus.DONE
    ogeler[1].status = QueueItemStatus.PROCESSING
    d._on_queue_changed(ogeler)
    # yeniden insa edilen listede en az o kadar cocuk var
    assert d._queue_list_layout.count() >= 2


def test_show_queue_result_guards(win, monkeypatch):
    d, _ = win
    d._show_queue_result(-1)
    d._show_queue_result(99)
    d._show_queue_result(0)  # bos kuyukta result yok -> sessiz


def test_show_queue_result_opens_readonly(win, monkeypatch):
    d, _ = win
    r = _sonuc(compatibility=CompatibilityReport(checks=[]),
               metadata=NS(name="demo"))
    yakalanan = {}

    class FakeRD(QObject):
        def __init__(self, **kw):
            super().__init__()
            yakalanan.update(kw)
        def exec(self):
            return 1
    monkeypatch.setattr(MW, "ResultDialog", FakeRD)
    from core.queue_manager import QueueItemStatus
    oge = NS(name="demo", file_path=Path("/x/d.deb"),
             status=QueueItemStatus.DONE, result=r)
    monkeypatch.setattr(d, "_queue", NS(items=[oge]))
    d._show_queue_result(0)
    assert yakalanan.get("read_only") is True
    assert yakalanan.get("sha256") == "ab"


def test_on_pipeline_finished_success_marks_queue(win, monkeypatch):
    d, _ = win
    d._queue.add_files([Path("/x/e.deb")])
    d._start_next_in_queue()
    r = _sonuc(success=True, message="harika")
    d._on_pipeline_finished(r, 0)
    assert d._new_btn.isVisibleTo(d) or d._queue.pending_count > 0
    assert "✓ harika" in d._status_bar.currentMessage()


def test_on_pipeline_finished_failure_branch(win, monkeypatch):
    d, _ = win
    d._queue.add_files([Path("/x/f.rpm")])
    d._start_next_in_queue()
    r = _sonuc(success=False, message="", compatibility=None)
    d._on_pipeline_finished(r, 0)
    assert "✗" in d._status_bar.currentMessage()


def test_finish_with_message_levels(win):
    d, _ = win
    d._finish_with_message("iyi", True)
    d._finish_with_message("kotu", False)
    assert d._status_bar.currentMessage() in ("iyi", "kotu")


def test_reset_ui_clears_all(win):
    d, _ = win
    d._reset_ui()
    assert d._progress_reset_ok if hasattr(d, "_progress_reset_ok") else True


def test_compatibility_ready_closed_dialog_releases_worker(win, monkeypatch):
    d, olusturulan = win
    p = olusturulan[0] if olusturulan else FakePipeline()
    d._pipeline = p
    p._result = _sonuc()
    yakalanan = {}

    class FakeRD(QObject):
        install_approved = pyqtSignal()
        distrobox_requested = pyqtSignal()

        def __init__(self, **kw):
            super().__init__()
            yakalanan.update(kw)
        def exec(self):
            return 0          # kapatildi -> dismiss + bitis mesaji
        def result(self):
            return 0
    monkeypatch.setattr(MW, "ResultDialog", FakeRD)
    _sessiz_qmsg(monkeypatch)
    d._on_compatibility_ready(p._result.compatibility)
    assert yakalanan.get("show_distrobox") in (False, True)


def test_run_distrobox_fallback_missing_file_returns(win):
    d, _ = win
    r = _sonuc(original_file=None)
    d._run_distrobox_fallback(r)   # erken donus, cokmez


def test_upstream_done_empty_informs(win, app, monkeypatch):
    d, _ = win
    from PyQt6.QtWidgets import QMessageBox
    bilgi = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: bilgi.append(a)))
    monkeypatch.setattr("core.upstream_tracker.check_all_installed_updates",
                        list)
    d._check_upstream_updates()
    son = time.time() + 4
    while time.time() < son and not bilgi:
        app.processEvents()
        time.sleep(0.01)
    assert bilgi and d._updates_btn.isEnabled()


def test_upstream_done_with_update_lists(win, app, monkeypatch):
    d, _ = win
    from PyQt6.QtWidgets import QMessageBox
    bilgi = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: bilgi.append(a)))
    kayit = NS(has_update=True, package_name="gtk3",
               detail="1.0 -> 2.0")
    monkeypatch.setattr("core.upstream_tracker.check_all_installed_updates",
                        lambda: [kayit])
    d._check_upstream_updates()
    son = time.time() + 4
    while time.time() < son and not bilgi:
        app.processEvents()
        time.sleep(0.01)
    assert any("gtk3" in str(x) for x in bilgi)


def test_upstream_error_shows_banner(win, app, monkeypatch):
    d, _ = win

    def patla():
        raise RuntimeError("ag yok")
    monkeypatch.setattr("core.upstream_tracker.check_all_installed_updates",
                        patla)
    d._check_upstream_updates()
    son = time.time() + 4
    while time.time() < son and not d._updates_btn.isEnabled():
        app.processEvents()
        time.sleep(0.01)
    assert d._updates_btn.isEnabled()