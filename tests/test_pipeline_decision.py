"""Tests for the ConversionPipeline install-decision gate.

The pipeline must block in _wait_for_decision() until the UI records a
choice, so the temp dir holding the converted package is not cleaned up
while the user reviews the compatibility report.
"""

import unittest

import pytest

# The pipeline (and this gate) needs a Qt event loop; skip cleanly where
# PyQt6 is not installed (the venv test suite runs without it).
pytest.importorskip("PyQt6")

from PyQt6.QtCore import QCoreApplication, QTimer  # noqa: E402

from core.pipeline import ConversionPipeline  # noqa: E402


def _ensure_app() -> QCoreApplication:
    """One shared QCoreApplication for all tests (Qt allows only one)."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


class TestPipelineDecisionGate(unittest.TestCase):

    def setUp(self):
        self.app = _ensure_app()
        self.pipeline = ConversionPipeline()

    def test_approve_before_wait_returns_true(self):
        # A decision recorded before the worker reaches the gate must not be
        # lost (no flag reset on entry).
        self.pipeline.approve_install()
        self.assertTrue(self.pipeline._wait_for_decision())

    def test_dismiss_before_wait_returns_false(self):
        self.pipeline.dismiss_install()
        self.assertFalse(self.pipeline._wait_for_decision())

    def test_dismiss_message_override(self):
        self.pipeline.dismiss_install("özel mesaj")
        self.assertEqual(self.pipeline._decision_message, "özel mesaj")

    def test_approve_wakes_blocked_wait(self):
        # The real wake-up path: worker blocked in the nested event loop,
        # UI thread records the decision shortly after.
        QTimer.singleShot(50, self.pipeline.approve_install)
        self.assertTrue(self.pipeline._wait_for_decision())

    def test_dismiss_wakes_blocked_wait(self):
        QTimer.singleShot(50, self.pipeline.dismiss_install)
        self.assertFalse(self.pipeline._wait_for_decision())

    def test_cancel_wakes_blocked_wait(self):
        # cancel() must release a worker blocked on the decision gate.
        QTimer.singleShot(50, self.pipeline.cancel)
        self.assertFalse(self.pipeline._wait_for_decision())
        self.assertTrue(self.pipeline._cancelled)

    def test_do_install_after_approval_is_approve_alias(self):
        self.pipeline.do_install_after_approval()
        self.assertTrue(self.pipeline._decision_approved)
        self.assertTrue(self.pipeline._decision_made)


if __name__ == "__main__":
    unittest.main()
