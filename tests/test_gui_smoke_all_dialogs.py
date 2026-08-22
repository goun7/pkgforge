"""Deep GUI smoke test: instantiate every dialog/widget and hammer with keys.

Guards against the class of crash found in ResultDialog (a signal/slot
signature mismatch that aborts the app when a key press auto-clicks a
focused button). Every widget is shown, given focus, and fed a battery of
key events; any unhandled exception or abort fails the test.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtWidgets import QApplication, QWidget
    _HAS_QT = True
except ImportError:
    _HAS_QT = False

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


KEYS = (
    Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space,
    Qt.Key.Key_Tab, Qt.Key.Key_Escape, Qt.Key.Key_A,
    Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right,
)


def _hammer(widget):
    """Send a battery of key events to a widget; raise on any exception.

    Buttons are set to non-default / non-auto-default first so that pressing
    Return/Space does NOT click them and open a modal QFileDialog (which would
    block this headless test). The dedicated toggle-crash regression tests in
    test_gui_crash_regressions.py cover the button-click path explicitly.
    """
    from PyQt6.QtWidgets import QAbstractButton

    app = _get_app()
    for btn in widget.findChildren(QAbstractButton):
        try:
            btn.setAutoDefault(False)
        except AttributeError:
            pass
        try:
            btn.setDefault(False)
        except AttributeError:
            pass
    widget.show()
    widget.setFocus()
    for key in KEYS:
        ev = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget, ev)
        app.processEvents()
    widget.close()


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestAllDialogsKeyHammer(unittest.TestCase):

    def test_confirm_dialog(self):
        _get_app()
        from ui.confirm_dialog import ConfirmDialog
        _hammer(ConfirmDialog("T", "M"))

    def test_about_dialog(self):
        _get_app()
        from ui.about_dialog import AboutDialog
        _hammer(AboutDialog())

    def test_settings_dialog(self):
        _get_app()
        from ui.settings_dialog import SettingsDialog
        _hammer(SettingsDialog())

    def test_history_dialog(self):
        _get_app()
        from ui.history_dialog import HistoryDialog
        _hammer(HistoryDialog())

    def test_url_dialog(self):
        _get_app()
        from ui.url_dialog import UrlDialog
        _hammer(UrlDialog())

    def test_result_dialog(self):
        _get_app()
        from core.compatibility_checker import (
            CheckResult,
            CheckSeverity,
            CompatibilityReport,
        )
        from core.package_analyzer import PackageMetadata
        from ui.result_dialog import ResultDialog
        report = CompatibilityReport(checks=[
            CheckResult("c", CheckSeverity.WARNING, "w", ["d1", "d2"]),
        ])
        meta = PackageMetadata(
            name="p", version="1-1", arch="amd64", arch_mapped="x86_64",
            description="d", file_list=["usr/bin/p"],
        )
        _hammer(ResultDialog(report=report, metadata=meta))

    def test_drop_zone(self):
        _get_app()
        from ui.drop_zone import DropZone
        _hammer(DropZone())

    def test_step_progress(self):
        _get_app()
        from ui.step_progress import StepProgress
        _hammer(StepProgress())

    def test_log_panel(self):
        _get_app()
        from ui.log_panel import LogPanel
        _hammer(LogPanel())

    def test_loading_indicator(self):
        _get_app()
        from ui.loading_indicator import LoadingIndicator
        _hammer(LoadingIndicator())

    def test_main_window(self):
        _get_app()
        from ui.main_window import MainWindow
        _hammer(MainWindow())


if __name__ == "__main__":
    unittest.main()
