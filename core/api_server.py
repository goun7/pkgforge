"""PkgForge — JSON-RPC 2.0 sidecar over stdio.

Framing: one JSON object per line on stdin/stdout. Logs go to stderr ONLY.
This module wraps the existing core modules; it adds NO new business logic.
"""
from __future__ import annotations

import json
import sys
import threading

from config import APP_NAME, APP_VERSION, discover_tools
from i18n import load_settings, save_settings

_write_lock = threading.Lock()


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


METHODS = {
    "app.version": handle_app_version,
    "tools.status": handle_tools_status,
    "settings.get": handle_settings_get,
    "settings.set": handle_settings_set,
}


def serve() -> None:
    """Run the sidecar main loop (blocking)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _error(None, -32700, "Parse error")
            continue
        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}
        handler = METHODS.get(method)
        if handler is None:
            _error(req_id, -32601, f"Method not found: {method}")
            continue
        try:
            _result(req_id, handler(params))
        except Exception as exc:  # noqa: BLE001 — report, never crash the loop
            _error(req_id, -32000, str(exc))
