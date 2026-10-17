"""Tur-40 — api_server SSE akisi, serve dallari ve kucuk handler artiklari."""
from __future__ import annotations

import http.client
import socket
import sys
import time
from types import SimpleNamespace as NS

import pytest

import core.api_server as AS


@pytest.fixture(scope="module")
def sse_sunucu():
    port = _serbest_port()

    def kos():
        AS.serve_http(port=port, token="op", host="127.0.0.1")
    eski = (AS._ensure_qapp, AS._ensure_scheduler, AS.restore_queue)
    AS.transport._ensure_qapp = lambda: None
    AS.handlers_queue._ensure_scheduler = lambda: None
    AS.handlers_queue.restore_queue = lambda: 0
    import threading
    threading.Thread(target=kos, daemon=True).start()
    for _ in range(100):
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            c.request("GET", "/health"); c.getresponse().read(); c.close()
            break
        except OSError:
            time.sleep(0.05)
    yield f"127.0.0.1:{port}"
    AS._ensure_qapp, AS._ensure_scheduler, AS.handlers_queue.restore_queue = eski


def _serbest_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_sse_publish_subscribe_units(monkeypatch):
    aboneler = []
    monkeypatch.setattr(AS.transport, "_sse_subscribers", aboneler)
    monkeypatch.setattr(AS.transport, "_sse_history", [])

    q = AS._sse_subscribe()                                        # 75-79
    assert q in aboneler

    AS._sse_publish("event/x", {"deger": 1})                       # 66-70
    assert q.get_nowait()["method"] == "event/x"
    assert AS.transport._sse_history[-1]["params"] == {"deger": 1}

    # dolu kuyruk sessizce yutulur
    dolu = NS(put_nowait=lambda p: (_ for _ in ()).throw(Exception("dolu")))
    aboneler.append(dolu)
    AS._sse_publish("event/y", {})                                 # 71-72

    AS._sse_unsubscribe(q)                                         # 82-85
    assert q not in aboneler
    AS._sse_unsubscribe(q)   # tekrar: yoksa da sorun degil


def test_sse_stream_replay_and_disconnect(sse_sunucu):
    host, port = sse_sunucu.split(":")
    sock = socket.create_connection((host, int(port)), timeout=10)
    istek = ("GET /events HTTP/1.1\r\n"
             "Host: x\r\n"
             "Authorization: Bearer op\r\n\r\n")
    sock.sendall(istek.encode())

    # gecmis kaydi yayinla, istemci okusun
    AS._sse_publish("event/once", {"sira": 1})
    tampon = b""
    while b"event/once" not in tampon and b"data:" not in tampon:
        parca = sock.recv(4096)
        if not parca:
            break
        tampon += parca
    assert b"event/once" in tampon or b"data:" in tampon           # 1525-1526

    # canli olay
    AS._sse_publish("event/canli", {"sira": 2})
    son = b""
    try:
        sock.settimeout(5)
        while b"event/canli" not in son:
            parca = sock.recv(4096)
            if not parca:
                break
            son += parca
    except OSError:
        pass
    # baglantiyi kir -> sunucu yaziminda OSError -> 1536-1537 + unsubscribe
    sock.close()
    AS._sse_publish("event/kirik", {"sira": 3})                    # tetikler
    time.sleep(0.2)


# --- stdin cerceveleme dallari ----------------------------------------------------

def _pump_kos(monkeypatch, parcalar, tick_hata=None):
    """_pump_stdin'i sahte okuyucuyla kosur; (yonlenen, hata) doner."""
    yonlenen: list[dict] = []
    monkeypatch.setattr(AS.protocol, "_route_request",
                        lambda msg: yonlenen.append(msg))

    def read():
        return parcalar.pop(0) if parcalar else None

    def tick():
        if tick_hata is not None:
            raise tick_hata

    hata = None
    try:
        AS.protocol._pump_stdin(read, AS.protocol._handle_line, tick)
    except BaseException as exc:                                    # noqa: BLE001
        hata = exc
    return yonlenen, hata


def test_pump_eof_donguyu_bitirir(monkeypatch):
    yonlenen, hata = _pump_kos(monkeypatch, [None])                # EOF dali
    assert yonlenen == [] and hata is None


def test_pump_bos_satirlar_atlanir(monkeypatch):
    yonlenen, hata = _pump_kos(monkeypatch, [b"   \n", b"\n", None])
    assert yonlenen == [] and hata is None


def test_pump_read_istisnasi_yukari_yayar(monkeypatch):
    """Yutma sozlesmesi _make_reader'in; _pump_stdin istisnayi saklamaz."""
    class Patlak:
        def pop(self, _i):
            raise ValueError("stdin kapali")

    yonlenen, hata = _pump_kos(monkeypatch, Patlak())
    assert yonlenen == [] and isinstance(hata, ValueError)


# --- kucuk handler artiklari ------------------------------------------------------

def test_pipeline_gate_handlers_with_active(monkeypatch):
    cagrilar = []
    monkeypatch.setattr(AS.transport, "_pipeline",
                        NS(cancel=lambda: cagrilar.append("c"),
                           approve_install=lambda: cagrilar.append("a"),
                           dismiss_install=lambda m: cagrilar.append(m)))
    AS.handle_pipeline_cancel({})
    AS.handle_pipeline_approve({})
    AS.handle_pipeline_dismiss({"message": "m"})                   # 151-164
    assert cagrilar == ["c", "a", "m"]


def test_security_small_handlers(monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")

    # monkeypatch.setitem: test bitince orijinal modul geri gelir.
    # Eskiden sys.modules.setdefault kullaniliyordu; gercek modul henuz
    # yuklenmemisse cubuk (NS) surekli kaliyor ve sonraki testlerde
    # "core.sigstore has no attribute" kirlenmesi yaratiyordu.
    monkeypatch.setitem(sys.modules, "core.package_signing", NS())
    ps = sys.modules["core.package_signing"]
    from dataclasses import dataclass

    @dataclass
    class Dogrulama:
        imzali: bool = True
    monkeypatch.setattr(ps, "verify_signature", lambda p: Dogrulama(),
                        raising=False)
    monkeypatch.setattr(ps, "list_keys", lambda: [{"ad": "k"}],
                        raising=False)
    yanit = AS.handle_security_verify({"pkg_path": str(pkg)})       # 213-218
    assert yanit["imzali"] is True
    assert AS.handle_security_keys({}) == [{"ad": "k"}]              # 221-224

    monkeypatch.setitem(sys.modules, "core.sigstore", NS())
    sg = sys.modules["core.sigstore"]
    monkeypatch.setattr(sg, "get_sigstore_status",
                        lambda: {"kurulu": False}, raising=False)
    assert AS.handle_security_sigstore_status({}) == {"kurulu": False}

    monkeypatch.setitem(sys.modules, "core.provenance", NS())
    pv = sys.modules["core.provenance"]
    monkeypatch.setattr(pv, "find_provenance",
                        lambda p: None, raising=False)
    belge = NS(to_dict=lambda: {"id": "p1"})
    monkeypatch.setattr(pv, "load_provenance",
                        lambda p: belge, raising=False)
    assert AS.handle_security_provenance(
        {"pkg_path": str(pkg)}) is None                              # 238-239

    monkeypatch.setattr(pv, "find_provenance",
                        lambda p: tmp_path / "p.json", raising=False)
    assert AS.handle_security_provenance(
        {"pkg_path": str(pkg)}) == {"id": "p1"}                      # 240-241