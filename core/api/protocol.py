"""PkgForge sidecar API — stdio dispatch protocol (F2.2 split)."""
from __future__ import annotations

import json
import os
import select
import sys
import threading
from collections.abc import Callable
from typing import Any

from core.api import handlers_queue, transport
from core.api.registry import METHODS
from i18n import tr

# Cercevesiz baytlar birikmesin: sinirsiz tampon, bozuk bir ebeveynde bellek
# buyumesine yol acar. Esik, en buykok yasal istekten (history.restore butun
# kayit lisesini tek satirda gonderir) buyuk secildi.
_MAX_INBOUND_BYTES = 8 * 1024 * 1024


def _dispatch(msg: dict[str, Any]) -> dict[str, Any]:
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


def _dispatch_blocking(msg: dict[str, Any]) -> None:
    """Bir handler'i stdin dongusunun disinda calistirir; yanit id ile eslestigi
    icin siralama onemsizdir, _send zaten _write_lock ile serilestirilir."""
    transport._send(_dispatch(msg))


def _route_request(msg: dict[str, Any]) -> None:
    """Bir istegi yonlendirir: pipeline el-sikma metodlari Qt signal affinity
    icin main thread'de senkron, diger handler'lar worker thread'de calisir ki
    yavas bir cagri stdin dongusunu ve Qt event dagitimini tikamasin."""
    if msg.get("method", "") in _MAIN_THREAD_METHODS:
        transport._send(_dispatch(msg))
    else:
        threading.Thread(target=_dispatch_blocking, args=(msg,), daemon=True).start()


def _handle_line(line: str) -> None:
    """Bir cercevelenmis istek satirini yollar."""
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        transport._error(None, -32700, "Parse error")
        return
    _route_request(msg)


ReadFn = Callable[[], bytes | None]


def _make_reader(fd: int, select_secs: float = 0.05) -> ReadFn:
    """fd'den chunk okuyan bir okuyucu.

    Donuş sözleşmesi: yeni bayt varsa baytlar, fd hazırsa ama akış kapandıysa
    `None`, henüz veri yoksa `b""` (çalışma zamanı boşta kalmasın diye).
    """
    def read() -> bytes | None:
        try:
            ready, _, _ = select.select([fd], [], [], select_secs)
            if not ready:
                return b""
            return os.read(fd, 65536) or None
        except (OSError, ValueError):
            return None  # ebeveyn stdin'i kapattı

    return read


def _pump_stdin(read: ReadFn, on_line: Callable[[str], None],
                tick: Callable[[], None] | None = None) -> None:
    """Chunk'lari satir cercevelerine cevirip `on_line` ile verir.

    `read()` yeni bayt verisiyse baytlari, hazir degilse `b""`, stdin
    kapandiysa `None` doner. `tick` her turda cagrilir (Qt olaylari icin).

    Cerceveleme burada, `select()` + `sys.stdin.readline()` ile degil: o
    ikili, ayni okumada gelen ikinci satiri TextIOWrapper tamponunda birakir
    ve fd bosaldigi icin select onu bir daha hazir goremez — istek, yeni bir
    satir gelene kadar yanitsiz kalir. Olculen 2026-10-17: `queue.add` ve
    `queue.start` arka arkaya yazilinca toplu kuyruk hic baslamadan takiliyordu.
    """
    buf = bytearray()
    while True:
        if tick is not None:
            tick()
        chunk = read()
        if chunk is None:
            return  # EOF / stdin kapandi
        if not chunk:
            continue
        buf.extend(chunk)
        if len(buf) > _MAX_INBOUND_BYTES:
            transport._error(None, -32700, tr("api.istem_satiri_cok_uzun"))
            buf.clear()
            continue
        while True:
            nl = buf.find(b"\n")
            if nl < 0:
                break
            line = bytes(buf[:nl]).decode("utf-8", "replace").strip()
            del buf[: nl + 1]
            if line:
                on_line(line)


def serve() -> None:
    """Run the sidecar main loop (blocking).

    Non-blocking stdin reads interleaved with Qt event processing so
    pipeline signals (emitted from a worker thread) are delivered and
    approve/dismiss requests reach a pipeline blocked in _wait_for_decision.
    """
    app = transport._ensure_qapp()
    handlers_queue._ensure_scheduler()
    handlers_queue.restore_queue()
    _pump_stdin(_make_reader(sys.stdin.fileno()), _handle_line, app.processEvents)
