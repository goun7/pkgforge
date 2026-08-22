"""PkgForge — JSON-RPC 2.0 sidecar over stdio.

Framing: one JSON object per line on stdin/stdout. Logs go to stderr ONLY.
This module wraps the existing core modules; it adds NO new business logic.
"""
from __future__ import annotations

import json
import sys
import threading

from pathlib import Path

from config import APP_NAME, APP_VERSION, discover_tools
from i18n import load_settings, save_settings

_write_lock = threading.Lock()

# Pipeline state (single conversion at a time, matching the GUI model)
_pipeline = None


def _send(obj: dict) -> None:
    with _write_lock:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _result(req_id, result):
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code, message):
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _event(method, params):
    _send({"jsonrpc": "2.0", "method": method, "params": params})


def handle_app_version(params):
    return {"name": APP_NAME, "version": APP_VERSION}


def handle_tools_status(params):
    tools = discover_tools()
    return {
        "has_pacman": bool(tools.pacman),
        "has_makepkg": bool(tools.makepkg),
        "has_distrobox": bool(getattr(tools, "distrobox", None)),
        "missing_required": list(tools.missing_required),
        "missing_optional": list(tools.missing_optional),
    }


def handle_settings_get(params):
    return load_settings()


def handle_settings_set(params):
    settings = load_settings()
    settings.update(params or {})
    save_settings(settings)
    return {"ok": True}


def _ensure_qapp():
    from PyQt6.QtCore import QCoreApplication

    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def handle_pipeline_start(params):
    global _pipeline
    from core.pipeline import ConversionPipeline

    path = Path(params.get("path", ""))
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    if path.suffix.lower() not in (".deb", ".rpm"):
        raise ValueError(f"Unsupported file type: {path.suffix}")
    _ensure_qapp()
    _pipeline = ConversionPipeline()
    _pipeline.step_changed.connect(
        lambda step, status: _event("event.step_changed", {"step": step, "status": status}))
    _pipeline.progress.connect(
        lambda v: _event("event.progress", {"value": v}))
    _pipeline.log_message.connect(
        lambda msg, level: _event("event.log", {"message": msg, "level": level}))
    _pipeline.compatibility_ready.connect(
        lambda report: _event("event.compatibility_ready", {"report": report.to_dict()}))
    _pipeline.finished.connect(
        lambda result: _event("event.finished", {"success": result.success, "message": result.message}))
    _pipeline.stage(path)
    # run on a worker thread so stdin keeps being read
    threading.Thread(target=_pipeline.run_staged, daemon=True).start()
    return {"started": True}


def handle_pipeline_cancel(params):
    if _pipeline:
        _pipeline.cancel()
    return {"ok": True}


def handle_pipeline_approve(params):
    if _pipeline:
        _pipeline.approve_install()
    return {"ok": True}


def handle_pipeline_dismiss(params):
    if _pipeline:
        _pipeline.dismiss_install(params.get("message", ""))
    return {"ok": True}


def handle_history_list(params):
    from core.history_db import HistoryDB

    db = HistoryDB()
    records = db.get_history(limit=int(params.get("limit", 100)))
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "package_name": r.package_name,
            "package_type": r.package_type,
            "status": r.status,
            "original_file": r.original_file,
            "source_url": r.source_url or "",
        }
        for r in records
    ]


def handle_history_uninstall(params):
    from core.security import is_valid_package_name

    name = params.get("name", "")
    if not is_valid_package_name(name):
        raise ValueError(f"Invalid package name: {name}")
    # Actual pacman -R requires privilege escalation; the desktop UI
    # triggers pkexec via its own privileged helper in a later phase.
    return {"ok": True, "requires_privilege": True, "package": name}


def handle_history_rollback(params):
    from core.history_db import HistoryDB
    from core.security import is_valid_package_name

    name = params.get("name", "")
    if not is_valid_package_name(name):
        raise ValueError(f"Invalid package name: {name}")
    db = HistoryDB()
    records = db.get_records_for_package(name)
    backups = [r for r in records if r.backup_pkg and Path(r.backup_pkg).is_file()]
    if not backups:
        raise FileNotFoundError(f"No backup found for {name}")
    return {"ok": True, "requires_privilege": True, "backup": backups[0].backup_pkg}


def handle_history_clear(params):
    from core.history_db import HistoryDB

    db = HistoryDB()
    db.clear_history()
    return {"ok": True}


METHODS = {
    "app.version": handle_app_version,
    "tools.status": handle_tools_status,
    "settings.get": handle_settings_get,
    "settings.set": handle_settings_set,
    "pipeline.start": handle_pipeline_start,
    "pipeline.cancel": handle_pipeline_cancel,
    "pipeline.approve": handle_pipeline_approve,
    "pipeline.dismiss": handle_pipeline_dismiss,
    "history.list": handle_history_list,
    "history.uninstall": handle_history_uninstall,
    "history.rollback": handle_history_rollback,
    "history.clear": handle_history_clear,
}


def _dispatch(msg: dict) -> None:
    req_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params") or {}
    handler = METHODS.get(method)
    if handler is None:
        _error(req_id, -32601, f"Method not found: {method}")
        return
    try:
        _result(req_id, handler(params))
    except Exception as exc:  # noqa: BLE001 — report, never crash the loop
        _error(req_id, -32000, str(exc))


def serve() -> None:
    """Run the sidecar main loop (blocking).

    Non-blocking stdin reads interleaved with Qt event processing so
    pipeline signals (emitted from the worker thread) are delivered and
    approve/dismiss requests reach a pipeline blocked in _wait_for_decision.
    """
    import select

    app = _ensure_qapp()
    while True:
        app.processEvents()
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0.05)
        except (OSError, ValueError):
            break  # stdin closed
        if not ready:
            continue
        line = sys.stdin.readline()
        if not line:
            break  # stdin closed — parent exited
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _error(None, -32700, "Parse error")
            continue
        _dispatch(msg)
