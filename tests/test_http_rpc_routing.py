"""HTTP RPC yol ayiramasi ve gecersiz-istek davranisi (gercek sunucu).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4 disinda kasitli GERCEK kosum: serve_http 127.0.0.1 uzerinde gercekten
baslatilir (test_api_server_http.py deseni), cunku yol ayiramasi bir HTTP
davranisidir; sahte nesnelerle test etmek ayni yanlisligi tekrarlar —
semada ilan edilen /rpc/<ad> yollarinin sunucuda HIC incelenmedigi tam da
boyle bir "yesil ama bos" testten firliyordu.
Ag disariya acilmaz (loopback), paket indirme/kurulum yapilmaz.

Onceki davranis (alt-ajan kaniti): do_POST `self.path`'e hic bakmiyordu;
`POST /totally-made-up` + govdede `method:"app.version"` -> 200 donerdi ve
`POST /rpc/security.verify` govdede baska bir method tasisa da 200 alirdi.
Ayrica govde JSON nesnesi degilse (ornek: dizi) `msg.get` AttributeError ile
handler's cakiyordu.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORT = 18799
TOKEN = "path-routing-token"


def _raw(body: bytes, path: str = "/", token: str | None = TOKEN):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 - non-JSON error body is itself a finding
            return e.code, {}


def _post(payload: dict, path: str = "/", token: str | None = TOKEN):
    return _raw(json.dumps(payload).encode("utf-8"), path, token)


@pytest.fixture
def server(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env.pop("XDG_CONFIG_HOME", None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve",
         "--http", "--port", str(PORT), "--token", TOKEN],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, text=True, env=env, cwd=str(PROJECT_ROOT))
    deadline = time.time() + 25
    up = False
    while time.time() < deadline:
        try:
            _post({"jsonrpc": "2.0", "id": 1, "method": "app.version",
                   "params": {}})
            up = True
            break
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    if not up:
        proc.kill()
        raise RuntimeError("HTTP sunucusu baslamadi")
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


# == ilan edilen yol gercekten isleniyor =======================================================

def test_rpc_yolu_govdeyle_ayni_oldugunda_calisir(server):
    """Semadaki /rpc/<ad> artik dekoratif degil: dogru eslesme 200."""
    code, body = _post({"jsonrpc": "2.0", "id": 1, "method": "app.version",
                        "params": {}}, path="/rpc/app.version")
    assert code == 200
    assert body["result"]["name"] == "PkgForge"


def test_rpc_yolu_ile_govde_method_uyusmuyorsa_red(server):
    """Yol yazimi + govde baska method -> tutarsizlik reddedilir."""
    code, body = _post({"jsonrpc": "2.0", "id": 2, "method": "app.version",
                        "params": {}}, path="/rpc/security.verify")
    assert code == 400
    assert body["error"]["code"] == -32600
    assert "Path/method mismatch" in body["error"]["message"]


def test_bilinmeyen_yol_artik_200_donmez(server):
    """`POST /totally-made-up` eskiden 200'du; simdi 404 + -32601."""
    code, body = _post({"jsonrpc": "2.0", "id": 3, "method": "app.version",
                        "params": {}}, path="/totally-made-up")
    assert code == 404
    assert body["error"]["code"] == -32601


def test_cakismali_yol_yazimi_prefix_kacagi_olamaz(server):
    """Onek oyunu: /rpc/app.version/../security.verify gibi yollar da reddedilir."""
    code, _body = _post({"jsonrpc": "2.0", "id": 4, "method": "app.version",
                         "params": {}}, path="/rpc/other%2Eapp.version")
    assert code in (400, 404)


def test_bos_rpc_prefix_kabul(server):
    """`/rpc` tek basina yol degildir; govdeye gore yonlendirme / ile ayni degil."""
    code, _body = _post({"jsonrpc": "2.0", "id": 5, "method": "app.version",
                         "params": {}}, path="/rpc")
    assert code == 200   # `/rpc` kök-yol esdegeri olarak serbest


# == geriyi e donuk uyum ======================================================================

def test_ciplak_yol_istemci_uyumu_korunur(server):
    """Mevcut istemciler (testler + Araci) govde-yontemli '/' kullanir."""
    code, body = _post({"jsonrpc": "2.0", "id": 6, "method": "app.version",
                        "params": {}}, path="/")
    assert code == 200 and body["result"]["name"] == "PkgForge"


def test_sorgu_dizesi_yol_uyusmesini_bozmamali(server):
    code, body = _post({"jsonrpc": "2.0", "id": 7, "method": "app.version",
                        "params": {}}, path="/rpc/app.version?x=1")
    assert code == 200
    assert body["result"]["name"] == "PkgForge"


# == gecersiz govde: cabuk yok, -32600 ========================================================

@pytest.mark.parametrize("govde", [
    b"[1, 2, 3]", b'"yalniz string"', b"42", b"true", b"null",
])
def test_nesne_olmayan_govde_invalid_request(server, govde):
    """ESKI DAVRANIS: msg.get -> AttributeError (handler cakiyordu)."""
    code, body = _raw(govde)
    assert code == 400
    assert body["error"]["code"] == -32600
    assert "Invalid Request" in body["error"]["message"]


def test_bos_govde_hala_parse_error(server):
    code, body = _raw(b"")
    assert code == 400
    assert body["error"]["code"] == -32700


def test_kimlik_dogrulama_once_kapali_yol_sonra(server):
    """Token yoksa yol/mehtep ne olursa 401 — auth, routing'den once gelir."""
    code, body = _post({"jsonrpc": "2.0", "id": 8, "method": "app.version",
                        "params": {}}, path="/rpc/app.version", token=None)
    assert code == 401
    assert body["error"]["message"] == "Unauthorized"
