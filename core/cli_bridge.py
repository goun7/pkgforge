"""PkgForge — CLI Bridge.

Provides synchronous wrappers around the converters so that the CLI
can run without PyQt6.

Two backends are supported:
- **subprocess** (default): Uses stdlib subprocess, no Qt dependency.
- **qt**: Uses QProcess via QCoreApplication in a daemon thread (legacy).

The subprocess backend is always preferred. Qt is only used as a
fallback when explicitly requested or when running in GUI mode.
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

from config import ToolPaths, discover_tools

log = logging.getLogger(__name__)


# ── Synchronous conversion result ──────────────────────────────

class ConversionResult:
    """Result of a synchronous CLI conversion."""

    __slots__ = ("success", "message", "output_pkg")

    def __init__(self) -> None:
        self.success: bool = False
        self.message: str = ""
        self.output_pkg: Path | None = None


# ── Subprocess-based conversion (no PyQt6) ────────────────────

def convert_deb_sync(
    deb_path: Path,
    output_dir: Path,
    tools: ToolPaths | None = None,
    *,
    progress_callback=None,
) -> ConversionResult:
    """Convert a .deb package synchronously using subprocess (no PyQt6)."""
    from core.subprocess_converters import NativeDebConverterSubprocess

    tools = tools or discover_tools()
    result = ConversionResult()

    converter = NativeDebConverterSubprocess(tools)
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
    """Convert an .rpm package synchronously using subprocess (no PyQt6)."""
    from core.subprocess_converters import RpmConverterSubprocess

    tools = tools or discover_tools()
    result = ConversionResult()

    converter = RpmConverterSubprocess(tools)
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


# ── Qt-based conversion (legacy, requires PyQt6) ───────────────

def _ensure_qt_app() -> None:
    """Create a QCoreApplication in a daemon thread (Qt backend only)."""
    import ctypes
    with threading.Lock():
        try:
            from PyQt6.QtCore import QCoreApplication
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication(sys.argv)
        except ImportError:
            return

        def _run_loop() -> None:
            app.exec()

        t = threading.Thread(target=_run_loop, daemon=True, name="qt-cli-loop")
        t.start()
