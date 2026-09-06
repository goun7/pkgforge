"""PkgForge sidecar API — stdio dispatch protocol (F2.2 split)."""
from __future__ import annotations

import json
import sys
import threading

from core.api import handlers_queue, transport
from core.api.registry import METHODS


def _dispatch(msg: dict) -> dict:
    """Dispatch one JSON-RPC request and return the response object.

    Returns the response dict (never raises) so both the stdio loop and the
    HTTP server can serialize it. Push events are emitted via _event().
    """
    req_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params") or {}
    handler = METHODS.get(method)
    if handler is None:
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}}
    try:
        return {"jsonrpc": "2.0", "id": req_id, "result": handler(params)}
    except Exception as exc:  # noqa: BLE001 — report, never crash the loop
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32000, "message": str(exc)}}


# Qt signal affinity si geregi pipeline el sikma metodlari stdin (main) thread'
# inde calismali; diger tum handler'lar worker thread'e alinir ki yavas bir
# cagri tum RPC dongusunu ve Qt event dagitimini tikamasin (Ayarlar takilmasi).
_MAIN_THREAD_METHODS = frozenset({
    "pipeline.start", "pipeline.approve", "pipeline.dismiss", "pipeline.cancel",
})


def _dispatch_blocking(msg: dict) -> None:
    """Bir handler'i stdin dongusunun disinda calistirir; yanit id ile eslestigi
    icin siralama onemsizdir, _send zaten _write_lock ile serilestirilir."""
    transport._send(_dispatch(msg))


def _route_request(msg: dict) -> None:
    """Bir istegi yonlendirir: pipeline el-sikma metodlari Qt signal affinity
    icin main thread'de senkron, diger handler'lar worker thread'de calisir ki
    yavas bir cagri stdin dongusunu ve Qt event dagitimini tikamasin."""
    if msg.get("method", "") in _MAIN_THREAD_METHODS:
        transport._send(_dispatch(msg))
    else:
        threading.Thread(target=_dispatch_blocking, args=(msg,), daemon=True).start()


def serve() -> None:
    """Run the sidecar main loop (blocking).

    Non-blocking stdin reads interleaved with Qt event processing so
    pipeline signals (emitted from the worker thread) are delivered and
    approve/dismiss requests reach a pipeline blocked in _wait_for_decision.
    """
    import select

    app = transport._ensure_qapp()
    handlers_queue._ensure_scheduler()
    handlers_queue.restore_queue()
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
            transport._error(None, -32700, "Parse error")
            continue
        _route_request(msg)
