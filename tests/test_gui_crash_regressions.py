"""Regression tests for GUI crashes found during deep component testing.

Bug 1 (CRASH): ResultDialog toggle closures were connected to clicked(bool).
  Pressing Enter/Space on a focused toggle button made QDialog::keyPressEvent
  click it, emitting clicked(False); the bool clobbered the captured widget
  default-arg -> AttributeError inside Qt event dispatch -> abort().

Bug 2 (threading): main_window connected QThread.started to a bare lambda,
  which PyQt queues onto the MAIN thread. The whole pipeline ran on the UI
  thread and created QProcess children across a thread-affinity boundary
  ("Cannot create children for a parent that is in a different thread").
  Fixed by staging the path and connecting to pipeline.run_staged (a slot of
  the already-moved object), which runs on the worker thread.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    _HAS_QT = True
except ImportError:
    _HAS_QT = False

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestResultDialogToggleCrash(unittest.TestCase):
    """Pressing activating keys on toggle buttons must not crash."""

    def _make_dialog(self):
        from core.compatibility_checker import (
            CheckResult,
            CheckSeverity,
            CompatibilityReport,
        )
        from core.package_analyzer import PackageMetadata
        from ui.result_dialog import ResultDialog

        report = CompatibilityReport(
            checks=[
                CheckResult(
                    name="test",
                    severity=CheckSeverity.WARNING,
                    message="warning",
                    details=["detail line 1", "detail line 2"],
                )
            ]
        )
        meta = PackageMetadata(
            name="hello",
            version="1.0.0-1",
            arch="amd64",
            arch_mapped="x86_64",
            description="test",
            file_list=["usr/bin/hello", "usr/share/hello/data.txt"],
        )
        return ResultDialog(report=report, metadata=meta)

    def test_files_toggle_survives_clicked_bool(self):
        """The files-card toggle must absorb clicked(bool) without raising."""
        _get_app()
        from PyQt6.QtWidgets import QPushButton

        dlg = self._make_dialog()
        toggles = [
            w for w in dlg.findChildren(QPushButton)
            if w.objectName() == "logToggle"
        ]
        self.assertTrue(toggles, "expected at least one logToggle button")
        for btn in toggles:
            # clicked() emits a bool; before the fix this raised AttributeError
            # and aborted the app. Now it must simply toggle visibility.
            btn.click()
            btn.click()
        dlg.close()

    def test_key_press_on_dialog_does_not_crash(self):
        """Simulate Enter/Space key presses reaching the dialog."""
        _get_app()
        from PyQt6.QtCore import QEvent, Qt
        from PyQt6.QtGui import QKeyEvent

        dlg = self._make_dialog()
        dlg.show()
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            ev = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(dlg, ev)
        dlg.close()


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestPipelineWorkerThread(unittest.TestCase):
    """run_staged must run the pipeline on the worker thread, not the UI thread."""

    def test_stage_sets_path(self):
        from pathlib import Path

        from core.pipeline import ConversionPipeline

        _get_app()
        p = ConversionPipeline()
        self.assertIsNone(p._staged_path)
        p.stage(Path("/tmp/foo.deb"))
        self.assertEqual(p._staged_path, Path("/tmp/foo.deb"))

    def test_run_staged_without_stage_emits_failure(self):
        from core.pipeline import ConversionPipeline

        _get_app()
        p = ConversionPipeline()
        results = []
        p.finished.connect(lambda r: results.append(r))
        p.run_staged()  # no staged path -> must fail gracefully, not crash
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)

    def test_run_staged_is_a_qt_slot(self):
        """run_staged must be a no-arg slot connectable to QThread.started."""
        import inspect

        from core.pipeline import ConversionPipeline

        sig = inspect.signature(ConversionPipeline.run_staged)
        # Only self; no positional file arg (QThread.started emits nothing).
        params = [p for p in sig.parameters.values() if p.name != "self"]
        self.assertEqual(params, [], "run_staged must take no args besides self")


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestResultDialogErrorInstallAnyway(unittest.TestCase):
    """ERROR (not recommended) reports must still offer Install Anyway.

    Previously the ERROR branch rendered only a Close button, so a user
    who wanted to proceed with a not-recommended package had no way to
    do so after closing the report. Both WARNING and ERROR now expose
    Close + Install Anyway.
    """

    def _make_dialog(self, severity):
        from core.compatibility_checker import (
            CheckResult,
            CompatibilityReport,
        )
        from core.package_analyzer import PackageMetadata
        from ui.result_dialog import ResultDialog

        report = CompatibilityReport(
            checks=[
                CheckResult(
                    name="test",
                    severity=severity,
                    message="msg",
                    details=["detail"],
                )
            ]
        )
        meta = PackageMetadata(
            name="hello",
            version="1.0.0-1",
            arch="amd64",
            arch_mapped="x86_64",
            description="test",
            file_list=["usr/bin/hello"],
        )
        return ResultDialog(report=report, metadata=meta)

    def _button_texts(self, dlg):
        from PyQt6.QtWidgets import QPushButton

        return {w.text() for w in dlg.findChildren(QPushButton)}

    def test_error_offers_install_anyway(self):
        """ERROR report must expose an Install Anyway button."""
        from core.compatibility_checker import CheckSeverity
        from i18n import tr

        _get_app()
        dlg = self._make_dialog(CheckSeverity.ERROR)
        texts = self._button_texts(dlg)
        self.assertIn(tr("btn.install_anyway"), texts)
        self.assertIn(tr("btn.close"), texts)
        dlg.close()

    def test_warning_offers_install_anyway(self):
        """WARNING report keeps Close + Install Anyway."""
        from core.compatibility_checker import CheckSeverity
        from i18n import tr

        _get_app()
        dlg = self._make_dialog(CheckSeverity.WARNING)
        texts = self._button_texts(dlg)
        self.assertIn(tr("btn.install_anyway"), texts)
        self.assertIn(tr("btn.close"), texts)
        dlg.close()

    def test_pass_offers_plain_install(self):
        """PASS report offers the plain Install button (no anyway)."""
        from core.compatibility_checker import CheckSeverity
        from i18n import tr

        _get_app()
        dlg = self._make_dialog(CheckSeverity.PASS)
        texts = self._button_texts(dlg)
        self.assertIn(tr("btn.install"), texts)
        self.assertNotIn(tr("btn.install_anyway"), texts)
        dlg.close()

    def test_error_install_anyway_emits_approved(self):
        """Clicking Install Anyway on an ERROR report emits install_approved."""
        from PyQt6.QtWidgets import QPushButton

        from core.compatibility_checker import CheckSeverity
        from i18n import tr

        _get_app()
        dlg = self._make_dialog(CheckSeverity.ERROR)
        approved = []
        dlg.install_approved.connect(lambda: approved.append(True))
        btn = next(
            w for w in dlg.findChildren(QPushButton)
            if w.text() == tr("btn.install_anyway")
        )
        btn.click()
        self.assertEqual(approved, [True])
        dlg.close()


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestResultDialogReadOnly(unittest.TestCase):
    """A reopened (read_only) report must show only Close, no install buttons.

    The converted package is cleaned up once the pipeline finishes, so an
    Install/Install Anyway button on a reopened report would be dead.
    """

    def _make_dialog(self, severity, read_only):
        from core.compatibility_checker import (
            CheckResult,
            CompatibilityReport,
        )
        from core.package_analyzer import PackageMetadata
        from ui.result_dialog import ResultDialog

        report = CompatibilityReport(
            checks=[
                CheckResult(
                    name="test",
                    severity=severity,
                    message="msg",
                    details=["detail"],
                )
            ]
        )
        meta = PackageMetadata(
            name="hello",
            version="1.0.0-1",
            arch="amd64",
            arch_mapped="x86_64",
            description="test",
            file_list=["usr/bin/hello"],
        )
        return ResultDialog(report=report, metadata=meta, read_only=read_only)

    def _button_texts(self, dlg):
        from PyQt6.QtWidgets import QPushButton

        return {w.text() for w in dlg.findChildren(QPushButton)}

    def test_read_only_error_shows_only_close(self):
        from core.compatibility_checker import CheckSeverity
        from i18n import tr

        _get_app()
        dlg = self._make_dialog(CheckSeverity.ERROR, read_only=True)
        texts = self._button_texts(dlg)
        self.assertIn(tr("btn.close"), texts)
        self.assertNotIn(tr("btn.install_anyway"), texts)
        self.assertNotIn(tr("btn.install"), texts)
        dlg.close()

    def test_read_only_pass_shows_only_close(self):
        from core.compatibility_checker import CheckSeverity
        from i18n import tr

        _get_app()
        dlg = self._make_dialog(CheckSeverity.PASS, read_only=True)
        texts = self._button_texts(dlg)
        self.assertIn(tr("btn.close"), texts)
        self.assertNotIn(tr("btn.install"), texts)
        dlg.close()


if __name__ == "__main__":
    unittest.main()
