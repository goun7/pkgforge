"""Tur-31 — api_server HTTP yuzeyi: gercek sunucu + http.client istemci."""
from __future__ import annotations

import http.client
import json
import socket
import threading
import time

import pytest

import core.api_server as AS


def _serbest_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def sunucu():
    port = _serbest_port()
    kanal = {"hazir": False}

    def kos():
        try:
            AS.serve_http(port=port, token="op-token", host="127.0.0.1",
                          read_token="read-token")
        finally:
            kanal["hazir"] = False

    eski_qapp = AS._ensure_qapp
    eski_sched = AS._ensure_scheduler
    eski_restore = AS.restore_queue
    AS.transport._ensure_qapp = lambda: None
    AS.handlers_queue._ensure_scheduler = lambda: None
    AS.handlers_queue.restore_queue = lambda: 0
    t = threading.Thread(target=kos, daemon=True)
    t.start()
    for _ in range(100):
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            c.request("GET", "/health")
            r = c.getresponse()
            if r.status == 200:
                r.read()
                c.close()
                break
            c.close()
        except OSError:
            time.sleep(0.05)
    else:
        raise RuntimeError("sunucu kalkmadi")
    yield f"127.0.0.1:{port}"
    # temizlik: thread daemon oldugu icin sonlanmasi beklenmez
    AS.transport._ensure_qapp = eski_qapp
    AS.handlers_queue._ensure_scheduler = eski_sched
    AS.handlers_queue.restore_queue = eski_restore


def _istek(sunucu_adres, method="POST", path="/", govde=None,
           basliklar=None):
    host, port = sunucu_adres.split(":")
    c = http.client.HTTPConnection(host, int(port), timeout=5)
    headers = dict(basliklar or {})
    payload = json.dumps(govde) if isinstance(govde, dict) else govde
    if payload is not None:
        headers.setdefault("Content-Type", "application/json")
    c.request(method, path, body=payload, headers=headers)
    yanit = c.getresponse()
    veri = yanit.read()
    c.close()
    try:
        return yanit.status, json.loads(veri)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return yanit.status, veri


def test_health(sunucu):
    kod, govde = _istek(sunucu, method="GET", path="/health")
    assert kod == 200 and govde["ok"] is True


def test_openapi_and_docs(sunucu):
    kod, sema = _istek(sunucu, method="GET", path="/openapi.json")
    assert kod == 200 and sema["openapi"].startswith("3.")
    kod, _ = _istek(sunucu, method="GET", path="/docs")
    assert kod == 200
    kod, _ = _istek(sunucu, method="GET", path="/")
    assert kod == 200
    kod, _ = _istek(sunucu, method="GET",
                    path="/assets/swagger/swagger-ui.css")
    assert kod == 200
    kod, _ = _istek(sunucu, method="GET",
                    path="/assets/swagger/swagger-ui-bundle.js")
    assert kod == 200


def test_unknown_path_404(sunucu):
    kod, _govde = _istek(sunucu, method="GET", path="/yok")
    assert kod == 404


def test_events_requires_auth(sunucu):
    kod, _govde = _istek(sunucu, method="GET", path="/events")
    assert kod == 401                                   # 1561-1562


def test_post_unauthorized(sunucu):
    kod, govde = _istek(sunucu, govde={"id": 1, "method": "app.version"})
    assert kod == 401 and govde["error"]["code"] == -32000      # 1576-1578


def test_post_operator_ok(sunucu):
    baslik = {"Authorization": "Bearer op-token"}
    kod, govde = _istek(sunucu, govde={"id": 7, "method": "app.version"},
                        basliklar=baslik)
    assert kod == 200 and govde["result"]["version"]


def test_post_reader_read_only_method(sunucu):
    baslik = {"Authorization": "Bearer read-token"}
    kod, _govde = _istek(sunucu, govde={"id": 8, "method": "app.version"},
                         basliklar=baslik)
    assert kod == 200


def test_post_reader_forbidden_write(sunucu):
    baslik = {"Authorization": "Bearer read-token"}
    kod, govde = _istek(sunucu, govde={"id": 9, "method": "settings.set",
                                       "params": {}}, basliklar=baslik)
    assert kod == 403 and govde["error"]["code"] == -32000      # 1593-1596


def test_post_parse_error(sunucu):
    baslik = {"Authorization": "Bearer op-token"}
    kod, govde = _istek(sunucu, govde="{bozuk", basliklar=baslik)
    assert kod == 400 and govde["error"]["code"] == -32700      # 1589-1591


def test_dispatch_unknown_and_exception():
    yanit = AS._dispatch({"id": 3, "method": "hic.birsey"})
    assert yanit["error"]["code"] == -32601                     # 1307-1309

    def patla(p):
        raise RuntimeError("patladi")
    eski = AS.METHODS.get("app.version")
    AS.METHODS["app.version"] = patla
    try:
        yanit = AS._dispatch({"id": 4, "method": "app.version"})
    finally:
        AS.METHODS["app.version"] = eski
    assert yanit["error"]["code"] == -32000                     # 1312-1314


def test_rate_limited_window(monkeypatch):
    AS._http_rate.clear()
    monkeypatch.setattr(AS.http, "_HTTP_RATE_LIMIT", 2)
    simdi = time.time()
    assert AS._rate_limited("1.1.1.1", simdi) is False
    assert AS._rate_limited("1.1.1.1", simdi) is False
    assert AS._rate_limited("1.1.1.1", simdi) is True           # 1371-1372
    # pencere disina tasinca tekrar izin
    assert AS._rate_limited("1.1.1.1", simdi + 61) is False     # 1369-1370


def test_resolve_client_ip():
    assert AS._resolve_client_ip("10.0.0.9", "1.2.3.4, 5.6.7.8",
                                 True) == "1.2.3.4"             # 1385-1386
    assert AS._resolve_client_ip("10.0.0.9", "1.2.3.4",
                                 False) == "10.0.0.9"           # 1387
    assert AS._resolve_client_ip("10.0.0.9", "", True) == "10.0.0.9"


def test_serve_http_guards():
    with pytest.raises(ValueError, match="--token"):
        AS.serve_http(port=1, host="0.0.0.0")                   # 1453-1456
    with pytest.raises(ValueError, match="--insecure-http-lan"):
        AS.serve_http(port=1, host="0.0.0.0", token="t")        # 1460-1464


def test_build_openapi_schema_shape():
    sema = AS.build_openapi_schema()
    assert "/rpc/app.version" in sema["paths"]
    girdi = sema["paths"]["/rpc/app.version"]["post"]
    assert girdi["operationId"] == "app_version"

def test_post_rate_limited_http(sunucu, monkeypatch):
    AS._http_rate.clear()
    monkeypatch.setattr(AS.http, "_HTTP_RATE_LIMIT", 1)
    baslik = {"Authorization": "Bearer op-token"}
    kod1, _ = _istek(sunucu, govde={"id": 20, "method": "app.version"},
                     basliklar=baslik)
    kod2, hata = _istek(sunucu, govde={"id": 21, "method": "app.version"},
                        basliklar=baslik)
    AS._http_rate.clear()
    assert kod1 == 200
    assert kod2 == 429 and hata["error"]["code"] == -32000      # 1570-1574


def test_post_body_too_large(sunucu):
    # Sunucu govdeyi OKUMADAN 413 doner; buyuk veriyi gercekten transfer
    # etmemek icin yalnizca Content-Length basligini abartiriz.
    host, port = sunucu.split(":")
    c = http.client.HTTPConnection(host, int(port), timeout=5)
    c.putrequest("POST", "/")
    c.putheader("Authorization", "Bearer op-token")
    c.putheader("Content-Type", "application/json")
    c.putheader("Content-Length", str(1_048_577))
    c.endheaders()
    c.send(b"{}")
    yanit = c.getresponse()
    govde = json.loads(yanit.read())
    c.close()
    assert yanit.status == 413                                   # 1582-1585
    assert govde["error"]["code"] == -32000