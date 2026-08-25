"""Coverage itmesi — core/api_server saf yardimcilar + dispatch + sema."""
from __future__ import annotations

import pytest

import core.api_server as API


def test_result_error_event(monkeypatch, capsys):
    monkeypatch.setattr(API, "_http_mode", False)
    sent = []
    monkeypatch.setattr(API, "_send", lambda obj: sent.append(obj))
    API._result(7, {"x": 1})
    API._error(8, -32000, "hata")
    API._event("event/test", {"p": 1})
    assert sent[0]["id"] == 7 and "result" in sent[0]
    assert sent[1]["error"]["code"] == -32000
    assert sent[2]["method"] == "event/test"

    monkeypatch.setattr(API, "_http_mode", True)
    pub = []
    monkeypatch.setattr(API, "_sse_publish", lambda m, p: pub.append((m, p)))
    API._event("event/x", {"y": 2})
    assert pub == [("event/x", {"y": 2})]

def test_send_real_stdout(capsys):
    API._send({"selam": True})
    out = capsys.readouterr().out
    assert out.startswith("{") and out.endswith("\n")

def test_require_pkg_file(tmp_path):
    f = tmp_path / "p.pkg.tar.zst"
    f.write_bytes(b"x")
    assert API._require_pkg_file({"pkg_path": str(f)}) == f
    with pytest.raises(FileNotFoundError):
        API._require_pkg_file({})

def test_validate_aur_name():
    API._validate_aur_name("demo-pkg")
    for bad in ("", "-bas", ".nokta", "bosluk ad", "x" * 256):
        with pytest.raises(ValueError):
            API._validate_aur_name(bad)

def test_dispatch(monkeypatch):
    r = API._dispatch({"id": 1, "method": "yok.boyle"})
    assert r["error"]["code"] == -32601 and "yok.boyle" in r["error"]["message"]

    monkeypatch.setitem(API.METHODS, "test.patla", lambda p: (_ for _ in ()).throw(RuntimeError("kirik")))
    r2 = API._dispatch({"id": 2, "method": "test.patla", "params": {}})
    assert r2["error"]["code"] == -32000 and "kirik" in r2["error"]["message"]

    monkeypatch.setitem(API.METHODS, "test.tamam", lambda p: "sonuc")
    r3 = API._dispatch({"id": 3, "method": "test.tamam"})
    assert r3["result"] == "sonuc" and r3["jsonrpc"] == "2.0"

def test_rate_limiter(monkeypatch):
    API._http_rate.clear()
    now = 1000.0
    limited = [API._rate_limited("ip1", now + i) for i in range(API._HTTP_RATE_LIMIT)]
    assert not any(limited)
    # Pencere hala dolu (ilk vuruş 1000, şimdi 1060 → 1060-1000 == 60, prune yok)
    assert API._rate_limited("ip1", now + API._HTTP_RATE_LIMIT) is True
    # eski kayitlar pencere disina cikinca tekrar izin verir
    assert API._rate_limited("ip1", now + 61 + API._HTTP_RATE_LIMIT) is False

def test_resolve_client_ip():
    assert API._resolve_client_ip("10.0.0.1", "", False) == "10.0.0.1"
    assert API._resolve_client_ip("10.0.0.1", "8.8.8.8, 10.0.0.9", False) == "10.0.0.1"
    assert API._resolve_client_ip("10.0.0.1", "8.8.8.8, 10.0.0.9", True) == "8.8.8.8"
    assert API._resolve_client_ip("10.0.0.1", "  ", True) == "10.0.0.1"

def test_methods_registry_and_openapi():
    names = sorted(API.METHODS)
    assert len(names) > 60
    assert all(callable(h) for h in API.METHODS.values())
    schema = API.build_openapi_schema()
    assert schema["openapi"] == "3.0.3"
    assert len(schema["paths"]) == len(names)
    sample = schema["paths"]["/rpc/" + names[0]]["post"]
    assert sample["operationId"] and sample["tags"]