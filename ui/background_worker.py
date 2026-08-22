"""PkgForge — Generic background worker for blocking operations.

Runs a callable on a dedicated QThread so the GUI never freezes during
network I/O (downloads, upstream update checks) or other blocking work.

Delivery guarantees:
  * `on_done(result)` / `on_error(message)` always run on the CALLING
    (UI) thread, via a receiver QObject that never leaves that thread.
  * The thread, worker, and receiver are kept in a module-level registry
    until the run settles, so garbage collection can never destroy a
    running QThread (which would abort the process).

Usage:
    run_in_background(
        fn=lambda: download_package(url),
        on_done=lambda path: ...,
        on_error=lambda msg: ...,
    )
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

log = logging.getLogger(__name__)

# Keeps (thread, worker, receiver) alive until each run settles. Without
# this, CPython GC could delete the QThread wrapper while the OS thread is
# still running, which Qt turns into a fatal abort.
_active_runs: set[tuple[QThread, QObject, QObject]] = set()


class _Worker(QObject):
    """Runs a single callable on its own thread and reports the outcome."""

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self._fn = fn

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            log.warning("Background worker failed: %s", exc)
            self.error.emit(str(exc))
        else:
            self.finished.emit(result)


class _Receiver(QObject):
    """Stays on the calling thread so callbacks are delivered there."""

    done = pyqtSignal(object)
    failed = pyqtSignal(str)


def run_in_background(
    fn: Callable[[], Any],
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> QThread:
    """Run *fn* on a background QThread; call back on the calling thread.

    Args:
        fn: Zero-argument callable to run off the UI thread.
        on_done: Called with fn()'s return value on success.
        on_error: Called with the exception message on failure.

    Returns:
        The started QThread (callers rarely need it; kept for tests).
    """
    thread = QThread()
    worker = _Worker(fn)
    worker.moveToThread(thread)
    receiver = _Receiver()  # never moved: lives on the calling thread
    _active_runs.add((thread, worker, receiver))

    # Cross-thread hop: worker signals are queued onto the receiver's
    # (calling) thread, so everything below runs on the UI thread.
    worker.finished.connect(receiver.done)
    worker.error.connect(receiver.failed)

    if on_done is not None:
        receiver.done.connect(on_done)
    if on_error is not None:
        receiver.failed.connect(on_error)

    def _cleanup() -> None:
        thread.quit()

    def _forget() -> None:
        _active_runs.discard((thread, worker, receiver))
        worker.deleteLater()
        receiver.deleteLater()

    receiver.done.connect(_cleanup)
    receiver.failed.connect(_cleanup)
    thread.finished.connect(_forget)

    thread.started.connect(worker.run)
    thread.start()
    return thread
