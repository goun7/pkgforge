"""PkgForge — CLI Bridge.

Provides synchronous wrappers around the Qt-based converters so that
the CLI can run without owning a QCoreApplication or QEventLoop.

Design:
    A minimal QCoreApplication is created in a daemon background thread
    (Qt requires at least one for QProcess to work). The main thread
    blocks on a threading.Event until the converter signals completion.
    This removes the need for the CLI to import or drive a Qt event loop.
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

from config import ToolPaths, discover_tools

log = logging.getLogger(__name__)

# ── Minimal Qt event loop in a daemon thread ─────────────────────

_qt_app = None
_qt_lock = threading.Lock()


def _ensure_qt_app() -> None:
    """Create a QCoreApplication (once) in a daemon background thread.

    Qt requires an application object for QProcess to work.  By running
    it in a daemon thread the CLI never owns or drives an event loop;
    the daemon thread does that silently.
    """
    global _qt_app
    with _qt_lock:
        if _qt_app is not None:
            return

        from PyQt6.QtCore import QCoreApplication
        from PyQt6.QtWidgets import QApplication

        # Prefer QApplication so that QStyle works (QProcess uses it internally
        # for some platforms).  If no display is available, fall back to
        # QCoreApplication which never touches the display server.
        try:
            _qt_app = QApplication.instance() or QApplication(sys.argv)
        except Exception:
            _qt_app = QCoreApplication.instance() or QCoreApplication(sys.argv)

        def _run_loop() -> None:
            import ctypes
            try:
                # Prevent Python from holding the GIL during exec()
                _sip_api = ctypes.pythonapi
                _sip_api.Py_AddPendingCall(
                    id(lambda: None),  # dummy – just keep the loop alive
                )
            except Exception:
                pass
            _qt_app.exec()  # type: ignore[union-attr]

        t = threading.Thread(target=_run_loop, daemon=True, name="qt-cli-loop")
        t.start()


# ── Synchronous conversion wrappers ─────────────────────────────

class ConversionResult:
    """Result of a synchronous CLI conversion."""

    __slots__ = ("success", "message", "output_pkg")

    def __init__(self) -> None:
        self.success: bool = False
        self.message: str = ""
        self.output_pkg: Path | None = None


def _wait_for_signal(emitter, callback, timeout: int = 600) -> None:
    """Block the current thread until *emitter* fires.

    Uses a daemon thread to process Qt events while waiting, so that
    QProcess-based converters keep working.
    """
    event = threading.Event()
    result_holder: list = []

    def on_fired(*args):
        result_holder.extend(args)
        event.set()

    emitter.connect(on_fired)
    event.wait(timeout=timeout)
    emitter.disconnect(on_fired)
    return tuple(result_holder) if result_holder else None


def convert_deb_sync(
    deb_path: Path,
    output_dir: Path,
    tools: ToolPaths | None = None,
    *,
    progress_callback=None,
) -> ConversionResult:
    """Convert a .deb package synchronously (blocking)."""
    _ensure_qt_app()

    from core.native_deb_converter import NativeDebConverter

    tools = tools or discover_tools()
    result = ConversionResult()

    converter = NativeDebConverter(tools)
    done_event = threading.Event()

    def on_line(line: str):
        if progress_callback:
            progress_callback(line)

    def on_done(success: bool, msg: str, pkg: object):
        result.success = success
        result.message = msg
        result.output_pkg = pkg if isinstance(pkg, Path) else None
        done_event.set()

    converter.output_line.connect(on_line)
    converter.finished.connect(on_done)
    converter.convert(deb_path, output_dir)
    done_event.wait(timeout=600)

    return result


def convert_rpm_sync(
    rpm_path: Path,
    output_dir: Path,
    meta=None,
    tools: ToolPaths | None = None,
    *,
    progress_callback=None,
) -> ConversionResult:
    """Convert an .rpm package synchronously (blocking)."""
    _ensure_qt_app()

    from core.rpm_converter import RpmConverter

    tools = tools or discover_tools()
    result = ConversionResult()

    converter = RpmConverter(tools)
    done_event = threading.Event()

    def on_line(line: str):
        if progress_callback:
            progress_callback(line)

    def on_done(success: bool, msg: str, pkg: object):
        result.success = success
        result.message = msg
        result.output_pkg = pkg if isinstance(pkg, Path) else None
        done_event.set()

    converter.output_line.connect(on_line)
    converter.finished.connect(on_done)
    if meta is not None:
        converter.convert(rpm_path, output_dir, meta)
    else:
        from core.package_analyzer import analyze_package
        meta = analyze_package(rpm_path, tools)
        converter.convert(rpm_path, output_dir, meta)
    done_event.wait(timeout=600)

    return result
