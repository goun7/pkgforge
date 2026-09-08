"""PkgForge sidecar API — HTTP/LAN transport + OpenAPI (F2.2 split)."""
from __future__ import annotations

import json
import queue
import sys
import time
from collections import deque

from config import APP_VERSION
from core import http_assets
from core.api import handlers_queue, transport
from core.api.protocol import _dispatch
from core.api.registry import METHODS
from core.capabilities import http_reader_methods as _http_reader_methods

# HTTP hardening limits (F4.2).
_HTTP_MAX_BODY = 1_048_576  # 1 MiB request body ceiling
_HTTP_RATE_LIMIT = 60  # requests per minute per client IP
# Methods a read-only token may call; everything else needs the operator token.
# F5.1: single source of truth lives in core/capabilities.py.

_READ_METHODS = _http_reader_methods()
_http_rate: dict[str, deque] = {}


def _rate_limited(ip: str, now: float) -> bool:
    """Sliding-window limiter: True when this client exceeded the cap."""
    # F5.2a: bounded memory — sweep empty per-IP buckets when map balloons.
    if len(_http_rate) > 4096:
        for stale in [k for k, v in _http_rate.items() if not v]:
            del _http_rate[stale]
    hits = _http_rate.setdefault(ip, deque())
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= _HTTP_RATE_LIMIT:
        return True
    hits.append(now)
    return False


def _resolve_client_ip(socket_ip: str, xff_header: str,
                       trusted_proxy: bool) -> str:
    """Pick the client IP used for rate limiting (F5.2b).

    X-Forwarded-For is honoured ONLY when the operator explicitly trusts an
    upstream (TLS-terminating) proxy; otherwise the header is attacker-
    controlled and would let anyone dodge the per-IP rate limit.
    """
    if trusted_proxy and xff_header:
        return xff_header.split(",")[0].strip() or socket_ip
    return socket_ip


def build_openapi_schema() -> dict:
    """Minimal OpenAPI 3 description of the JSON-RPC surface (F4.8).

    Method names and doc summaries are public metadata by design; executing
    methods still requires the operator/read tokens enforced in do_POST.
    """
    paths: dict = {}
    for name in sorted(METHODS):
        handler = METHODS[name]
        doc = (getattr(handler, "__doc__", None) or "").strip()
        summary = doc.splitlines()[0] if doc else "JSON-RPC metodu: " + name
        paths["/rpc/" + name] = {
            "post": {
                "operationId": name.replace(".", "_"),
                "summary": summary,
                "tags": [name.split(".")[0]],
                "requestBody": {
                    "required": False,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "params": {"type": "object",
                                       "additionalProperties": True},
                        },
                    }}}},
                "responses": {
                    "200": {"description": "JSON-RPC yanıtı"},
                    "401": {"description": "token gerekli"},
                    "403": {"description": "okuma yetkisi yok"},
                    "429": {"description": "hız limiti"},
                },
            }
        }
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "PkgForge API",
            "version": APP_VERSION,
            "description": ("JSON-RPC yüzeyi. Yazma işlemleri operator "
                            "token, salt-okuma metodları read-token ile "
                            "açılır."),
        },
        "servers": [{"url": "/"}],
        "paths": paths,
    }


def _http_validate_bind(host: str, token: str, insecure_http_lan: bool) -> None:
    """F5.2b: LAN baglama guvenlik on kosullari (serve_http baslangici).

    Loopback olmayan adres: token zorunlu; acik HTTP bilincli onay ister.
    """
    loopback = host in ("127.0.0.1", "localhost", "::1")
    if not loopback and not token:
        raise ValueError(
            "Non-loopback bind requires --token "
            "(LAN erisimi kimlik dogrulamasiz acilamaz)")
    # F5.2b: no TLS support — plain HTTP on a routable address is only
    # allowed behind an explicit opt-in, or in front of a TLS-terminating
    # reverse proxy (use --trusted-proxy so X-Forwarded-For is honoured).
    if not loopback and not insecure_http_lan:
        raise ValueError(
            "Non-loopback HTTP requires --insecure-http-lan "
            "(TLS yok; acik HTTP LAN erisimi icin riski bilincli onaylayin "
            " ya da onde TLS sonlandiran bir reverse proxy kullanin)")


def _make_http_handler(token: str, read_token: str, trusted_proxy: bool) -> type:
    """serve_http icin istek isleyici sinifini uret (kimlik kapsami kapali)."""
    import hmac
    from http.server import BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, obj: dict) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _scope(self) -> str | None:
            """Return operator/reader for this request, else None."""
            auth = self.headers.get("Authorization", "")
            if token and hmac.compare_digest(auth, f"Bearer {token}"):
                return "operator"
            if read_token and hmac.compare_digest(auth, f"Bearer {read_token}"):
                return "reader"
            return None

        def _client_ip(self) -> str:
            """Client address for rate limiting.

            F5.2b: only honour X-Forwarded-For when the operator explicitly
            trusts an upstream proxy; otherwise the header is attacker-controlled.
            """
            return _resolve_client_ip(
                self.client_address[0],
                self.headers.get("X-Forwarded-For", ""),
                trusted_proxy)

        def _raw(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _sse_write(self, ev: dict) -> None:
            data = json.dumps(ev, ensure_ascii=False)
            self.wfile.write(f"event: message\ndata: {data}\n\n".encode())
            self.wfile.flush()

        def _sse_stream(self) -> None:
            """F5.23: stream push events as Server-Sent Events."""
            q = transport._sse_subscribe()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                # Replay recent history so late clients catch up.
                with transport._sse_lock:
                    history = list(transport._sse_history)
                for ev in history:
                    self._sse_write(ev)
                # Stream new events until the client disconnects.
                while True:
                    try:
                        ev = q.get(timeout=15)
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        continue
                    self._sse_write(ev)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                transport._sse_unsubscribe(q)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._reply(200, {"ok": True, "service": "pkgforge-http",
                                  "version": APP_VERSION})
            elif self.path == "/openapi.json":
                self._raw(200, json.dumps(build_openapi_schema()).encode(),
                          "application/json")
            elif self.path == "/docs":
                self._raw(200, http_assets.docs_html(),
                          "text/html; charset=utf-8")
            elif self.path in ("/", "/index.html"):
                self._raw(200, http_assets.dashboard_html(),
                          "text/html; charset=utf-8")
            elif self.path == "/assets/swagger/swagger-ui.css":
                self._raw(200, http_assets.swagger_css(), "text/css")
            elif self.path == "/assets/swagger/swagger-ui-bundle.js":
                self._raw(200, http_assets.swagger_bundle_js(),
                          "application/javascript")
            elif self.path == "/events":
                # F5.23: SSE canli olay akisi (reader ya da operator token).
                if self._scope() is None:
                    self._reply(401, {"error": "Unauthorized"})
                    return
                self._sse_stream()
            else:
                self._reply(404, {"error": "not found"})

        def do_POST(self) -> None:
            client_ip = self._client_ip()
            if _rate_limited(client_ip, time.time()):
                self._reply(429, {"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32000,
                                            "message": "Rate limit exceeded"}})
                return
            scope = self._scope()
            if scope is None:
                self._reply(401, {"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32000, "message": "Unauthorized"}})
                return
            length = int(self.headers.get("Content-Length", 0))
            if length > _HTTP_MAX_BODY:
                self._reply(413, {"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32000,
                                            "message": "Request body too large"}})
                return
            raw = self.rfile.read(length) if length else b""
            try:
                msg = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._reply(400, {"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32700, "message": "Parse error"}})
                return
            if scope == "reader" and msg.get("method") not in _READ_METHODS:
                self._reply(403, {"jsonrpc": "2.0", "id": msg.get("id"),
                                  "error": {"code": -32000,
                                            "message": "Read-only token"}})
                return
            self._reply(200, _dispatch(msg))

        def log_message(self, fmt: object, *args: object) -> None:
            pass  # silence per-request logging

    return Handler


def serve_http(port: int = 8765, token: str = "", host: str = "127.0.0.1",
               read_token: str = "", insecure_http_lan: bool = False,
               trusted_proxy: bool = False) -> None:
    """Run the JSON-RPC API over HTTP for LAN remote management (B7/F4.2).

    POST / accepts a single JSON-RPC 2.0 request and returns the response.
    Requests must carry "Authorization: Bearer <token>" (operator scope) or
    the optional *read_token* (read-only method subset). Binding to a
    non-loopback address without an operator token is refused at startup.
    Push events are suppressed in this mode (no stdio channel).
    """
    from http.server import ThreadingHTTPServer

    _http_validate_bind(host, token, insecure_http_lan)

    transport._http_mode = True
    transport._ensure_qapp()
    handlers_queue._ensure_scheduler()
    handlers_queue.restore_queue()

    Handler = _make_http_handler(token, read_token, trusted_proxy)
    server = ThreadingHTTPServer((host, port), Handler)
    sys.stderr.write(f"[http] JSON-RPC dinleniyor: http://{host}:{port}/\n")
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
