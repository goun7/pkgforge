"""PkgForge sidecar API — transport: shared state, SSE bus, JSON-RPC framing (F2.2 split)."""
from __future__ import annotations

import json
import queue
import sys
import threading
from collections import deque
from pathlib import Path

_write_lock = threading.Lock()

# Pipeline state (single conversion at a time, matching the GUI model)
_pipeline = None

# When True (HTTP/LAN mode) push events have no stdio channel to ride on,
# so _event() suppresses them instead of polluting the server's stdout.
_http_mode = False
# F5.23: SSE (Server-Sent Events) event bus for the HTTP dashboard. A ring
# buffer keeps recent events for late subscribers; each connected /events
# client gets its own queue. Publishing is best-effort and never blocks the
# conversion pipeline.
_sse_lock = threading.Lock()
_sse_history: deque = deque(maxlen=100)
_sse_subscribers: list = []
def _sse_publish(method, params):
    """Broadcast a push event to SSE subscribers + the ring buffer."""
    payload = {"method": method, "params": params}
    with _sse_lock:
        _sse_history.append(payload)
        for q in _sse_subscribers:
            try:
                q.put_nowait(payload)
            except Exception:  # noqa: BLE001, S110 - full/dead subscriber
                pass


def _sse_subscribe():
    q = queue.Queue(maxsize=256)
    with _sse_lock:
        _sse_subscribers.append(q)
    return q


def _sse_unsubscribe(q):
    with _sse_lock:
        if q in _sse_subscribers:
            _sse_subscribers.remove(q)
def _send(obj: dict) -> None:
    with _write_lock:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _result(req_id, result):
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code, message):
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _event(method, params):
    if _http_mode:
        # F5.23: no stdio channel in HTTP mode; broadcast over SSE instead.
        _sse_publish(method, params)
        return
    _send({"jsonrpc": "2.0", "method": method, "params": params})


def _ensure_qapp():
    from PyQt6.QtCore import QCoreApplication

    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app
# ── Faz 1 / A2: security panel ──────────────────────────────────

def _require_pkg_file(params) -> Path:
    """Resolve and validate a package path param, raising if missing."""
    path = Path(params.get("pkg_path", ""))
    if not path.is_file():
        raise FileNotFoundError(f"Package not found: {path}")
    return path
def _run_thread(fn, event_name):
    """Run a blocking op on a daemon thread, emitting a done event.

    The done event carries {"ok": True, "result": ...} on success or
    {"ok": False, "error": str} on failure. Used by all long-running
    Faz 1 handlers (export, graph, source, system).
    """

    def _worker():
        try:
            result = fn()
            _event(event_name, {"ok": True, "result": result})
        except Exception as exc:  # noqa: BLE001
            _event(event_name, {"ok": False, "error": str(exc)})

    threading.Thread(target=_worker, daemon=True).start()


def _run_security_thread(fn, event_name="event/security_done"):
    """Backwards-compatible alias for security ops."""
    _run_thread(fn, event_name)
