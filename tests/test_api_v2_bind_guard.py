"""api_v2 loopback-only bind guard + serve-api temiz reddetme testleri.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: uvicorn MODUL DUZEYINDE patch'lenir — gercek sunucu baslamaz, port
         dinlenmez, ag yok.

Neden var: core/api_v2.py'da HICBIR kimlik dogrulama yok (token/TLS yok), ama
`run(host=...)` verilen adresi dogrudan uvicorn'e akiyordu. Gozlem:
`main.py serve-api --host 0.0.0.0` uvicorn'in bind asamasina ulasiyordu
(rc=3 = izin hatasi) — yani bir koruma degil, kazara basarisizlik. Intentional
bir `--host 0.0.0.0` ile bu yuzey ag/açik laboratuvara kimlik dogrulamasiz
`POST /api/v2/benchmark` gibi mutate eden uclarla acilirkti.
Karsilastirma: çekirdek sidecar (core/api/http.py) ayni durumda
_http_validate_bind ile token + bilincli onay istiyor; api_v2'de token
mekanimasi OLMADIGI icin burada dogru davranis routable bind'i tamamen reddetmek.
"""
from __future__ import annotations

import argparse
import sys
import types

import pytest

import cli
from core.api_v2 import _LOOPBACK_HOSTS, ensure_bind_allowed, run


@pytest.fixture
def uvicorn_stub(monkeypatch):
    """uvicorn.run'i kaydeden sahte modül; gercek sunucu YOK."""
    started: list[dict] = []
    mod = types.ModuleType("uvicorn")
    mod.run = lambda app, host, port, log_level: started.append(
        {"host": host, "port": port})
    monkeypatch.setitem(sys.modules, "uvicorn", mod)
    return started


# == guard birimi ==============================================================================

@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "10.0.0.5",
                                  "example.org", "0.0.0.1", "", None])
def test_routable_bind_reddedilir(host, uvicorn_stub):
    with pytest.raises(ValueError):
        ensure_bind_allowed(host if host is not None else "")
    assert uvicorn_stub == [], "reddedilen bind yine de uvicorn'i baslatti"


@pytest.mark.parametrize("host", sorted(_LOOPBACK_HOSTS))
def test_loopback_bind_kabul_edilir(host, uvicorn_stub):
    ensure_bind_allowed(host)
    assert uvicorn_stub == []


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_run_loopback_uvicorni_baseline_calistirir(host, uvicorn_stub):
    run(host=host, port=8899)
    assert uvicorn_stub == [{"host": host, "port": 8899}]


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.0.10"])
def test_run_routable_bindde_uvicorn_cagrilmaz(host, uvicorn_stub):
    with pytest.raises(ValueError):
        run(host=host, port=8899)
    assert uvicorn_stub == []


def test_hata_mesaji_alternatifi_gosteriyor():
    """Reddetme mesaji kullaniciya NE yapacagini soylemeli."""
    with pytest.raises(ValueError) as ei:
        ensure_bind_allowed("0.0.0.0")
    msg = str(ei.value)
    assert "127.0.0.1" in msg
    assert "pkgforge serve" in msg        # token'li yuzeye yonlendirme
    assert "0.0.0.0" in msg               # hangi adres reddedildi


# == CLI yuzeyi ================================================================================

def _ns(**kw) -> argparse.Namespace:
    base = {"host": "127.0.0.1", "port": 8899, "export_openapi": None}
    base.update(kw)
    return argparse.Namespace(**base)


def test_cli_temiz_redde_izlek_yok(monkeypatch, capsys):
    """Kullanici hatasi tek satir olmali; traceback UX degil."""
    monkeypatch.delitem(sys.modules, "uvicorn", raising=False)
    rc = cli._cmd_serve_api(_ns(host="0.0.0.0"))
    out = capsys.readouterr()
    assert rc == 1
    assert "❌" in out.err
    assert "Traceback" not in out.err + out.out


def test_cli_rededilince_banner_basilmaz(monkeypatch, capsys):
    """Banner'dan ONCE dogrulama: URL soyu verildikten sonra reddedilmemeli."""
    monkeypatch.delitem(sys.modules, "uvicorn", raising=False)
    rc = cli._cmd_serve_api(_ns(host="0.0.0.0"))
    out = capsys.readouterr().out
    assert rc == 1
    assert "🚀" not in out
    assert "Docs:" not in out


def test_cli_loopback_banner_baseline_ve_sunucuya_ilerler(monkeypatch, capsys):
    started: list[dict] = []
    mod = types.ModuleType("uvicorn")
    mod.run = lambda app, host, port, log_level: started.append(
        {"host": host, "port": port})
    monkeypatch.setitem(sys.modules, "uvicorn", mod)
    rc = cli._cmd_serve_api(_ns(host="127.0.0.1", port=8899))
    out = capsys.readouterr().out
    assert rc == 0
    assert "http://127.0.0.1:8899" in out
    assert started == [{"host": "127.0.0.1", "port": 8899}]


def test_cli_host_veyok_varsayilani_loopback(monkeypatch, capsys):
    """Eski/eksik Namespace: host alani yoksa loopback varsayilani guvenli."""
    started: list[dict] = []
    mod = types.ModuleType("uvicorn")
    mod.run = lambda app, host, port, log_level: started.append(host)
    monkeypatch.setitem(sys.modules, "uvicorn", mod)
    rc = cli._cmd_serve_api(argparse.Namespace())
    assert rc == 0
    assert started == ["127.0.0.1"]


# == docstring yol iddiasi =====================================================================

def test_docs_ve_schema_yollari_docstring_ile_ayni():
    """/api/v2/docs 404'tu; docstring gercek yollari soylemeli."""
    import core.api_v2 as A

    doc = A.__doc__ or ""
    assert "/docs (Swagger UI)" in doc
    assert "/api/v2/docs" not in doc
    assert "/openapi.json" in doc
