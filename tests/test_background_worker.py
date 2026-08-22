"""Tests for the GUI background worker (off-thread blocking operations).

Covers the helper that keeps the GUI responsive during network I/O:
success and error paths, plus the threaded UrlDialog download flow.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QEventLoop, QTimer
    from PyQt6.QtWidgets import QApplication

    _HAS_QT = True
except Exception:  # noqa: BLE001
    _HAS_QT = False


_app = None


def _get_app():
    """Return a process-wide QApplication, holding a global reference.

    Without the module-level reference the QApplication wrapper can be
    garbage-collected, destroying the C++ QApplication and making any later
    widget construction abort ("Must construct a QApplication...").
    """
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestRunInBackground(unittest.TestCase):
    """run_in_background must deliver results/errors on the UI thread."""

    def _wait(self, predicate, timeout_ms=3000):
        """Spin the event loop until predicate() is true or timeout."""
        _get_app()
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)

        checker = QTimer()
        checker.setInterval(10)

        def _check():
            if predicate():
                loop.quit()

        checker.timeout.connect(_check)
        checker.start()
        timer.start(timeout_ms)
        loop.exec()
        checker.stop()
        return predicate()

    def test_success_delivers_result(self):
        from ui.background_worker import run_in_background

        _get_app()
        got = []
        run_in_background(fn=lambda: 42, on_done=got.append)
        self.assertTrue(self._wait(lambda: bool(got)))
        self.assertEqual(got, [42])

    def test_error_delivers_message(self):
        from ui.background_worker import run_in_background

        _get_app()
        errs = []

        def _boom():
            raise ValueError("kaput")

        run_in_background(fn=_boom, on_error=errs.append)
        self.assertTrue(self._wait(lambda: bool(errs)))
        self.assertIn("kaput", errs[0])

    def test_runs_off_ui_thread(self):
        """The callable must execute on a thread other than the UI thread."""
        import threading

        from ui.background_worker import run_in_background

        _get_app()
        seen = []
        ui_thread = threading.get_ident()
        run_in_background(fn=lambda: seen.append(threading.get_ident()), on_done=lambda _r: None)
        self.assertTrue(self._wait(lambda: bool(seen)))
        self.assertNotEqual(seen[0], ui_thread)


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestUrlDialogThreadedDownload(unittest.TestCase):
    """UrlDialog must download off the UI thread and not freeze."""

    def _wait(self, predicate, timeout_ms=3000):
        _get_app()
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        checker = QTimer()
        checker.setInterval(10)

        def _check():
            if predicate():
                loop.quit()

        checker.timeout.connect(_check)
        checker.start()
        timer.start(timeout_ms)
        loop.exec()
        checker.stop()
        return predicate()

    def test_success_emits_file_downloaded(self):
        from unittest.mock import patch

        from ui.url_dialog import UrlDialog

        _get_app()
        dlg = UrlDialog()
        dlg._url_input.setText("https://example.com/pkg.deb")

        got = []
        dlg.file_downloaded.connect(got.append)

        with patch("ui.url_dialog.download_package", return_value="/tmp/pkg.deb"):
            dlg._start_download()
            self.assertTrue(self._wait(lambda: bool(got)))

        self.assertEqual(got, ["/tmp/pkg.deb"])
        dlg.close()

    def test_error_reenables_button(self):
        from unittest.mock import patch

        from ui.url_dialog import UrlDialog

        _get_app()
        dlg = UrlDialog()
        dlg._url_input.setText("https://example.com/pkg.deb")

        def _fail(url, require_https=True):
            raise RuntimeError("net down")

        # Suppress the modal error box so the test does not block.
        with patch("ui.url_dialog.download_package", side_effect=_fail), \
             patch("ui.url_dialog.QMessageBox.critical"):
            dlg._start_download()
            self.assertTrue(self._wait(lambda: dlg._download_btn.isEnabled()))

        self.assertTrue(dlg._download_btn.isEnabled())
        dlg.close()


if __name__ == "__main__":
    unittest.main()