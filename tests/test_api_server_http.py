"""Faz 2 (B7) tests — JSON-RPC over HTTP (serve_http)."""
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
PORT = 18765
TOKEN = "test-secret-token"


@pytest.fixture
def http_server(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env.pop("XDG_CONFIG_HOME", None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve",
         "--http", "--port", str(PORT), "--token", TOKEN],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, text=True, env=env,
        cwd=str(PROJECT_ROOT),
    )
    # wait for the server to come up
    deadline = time.time() + 20
    up = False
    while time.time() < deadline:
        try:
            _post({"jsonrpc": "2.0", "id": 1, "method": "app.version", "params": {}}, TOKEN)
            up = True
            break
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    if not up:
        proc.kill()
        raise RuntimeError("HTTP server did not start")
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _post(payload: dict, token: str | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
        return json.loads(resp.read().decode("utf-8"))


def test_http_app_version(http_server):
    resp = _post({"jsonrpc": "2.0", "id": 1, "method": "app.version", "params": {}}, TOKEN)
    assert resp["result"]["name"] == "PkgForge"


def test_http_rejects_missing_token(http_server):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post({"jsonrpc": "2.0", "id": 1, "method": "app.version", "params": {}}, None)
    assert exc.value.code == 401


def test_http_rejects_wrong_token(http_server):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post({"jsonrpc": "2.0", "id": 1, "method": "app.version", "params": {}}, "wrong")
    assert exc.value.code == 401


def test_http_unknown_method(http_server):
    resp = _post({"jsonrpc": "2.0", "id": 2, "method": "nope.nope", "params": {}}, TOKEN)
    assert resp["error"]["code"] == -32601


def test_http_bad_json(http_server):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/",
        data=b"not json",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {TOKEN}"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=10)  # nosec B310
    assert exc.value.code == 400


# --- F4.2: hardening ---------------------------------------------------------

def _get(path: str, token: str | None = TOKEN) -> tuple[int, dict]:
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {}


def test_health_endpoint_needs_no_auth(http_server):
    status, body = _get("/health", token=None)
    assert status == 200
    assert body["ok"] is True
    assert body["service"] == "pkgforge-http"


def test_non_loopback_bind_requires_token():
    from core.api_server import serve_http

    with pytest.raises(ValueError, match="token"):
        serve_http(host="0.0.0.0", port=1, token="")


def test_body_over_1mib_rejected(http_server):
    big = b"x" * (1_048_576 + 1)
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/",
        data=big,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {TOKEN}"},
        method="POST",
    )
    # Yarissiz degil: sunucu govdeyi OKUMADAN 413 donup baglantiyi kapar;
    # yuk altinda istemci ya HTTPError 413 alir ya da yazma tarafinda
    # ConnectionReset/BrokenPipe gorur. Ikisi de gecerli bir "reddedildi"
    # kanitidir; onemli olan istismarin kabul edilmemesidir.
    try:
        urllib.request.urlopen(req, timeout=30)  # nosec B310
        pytest.fail("1MiB+ govde reddedilmedi")
    except urllib.error.HTTPError as exc:
        assert exc.code == 413
    except (urllib.error.URLError, ConnectionError, BrokenPipeError, OSError) as exc:
        reason = str(getattr(exc, "reason", exc)).lower()
        assert any(k in reason for k in ("reset", "broken pipe", "connection")), reason


def test_read_only_token_scope(tmp_path):
    import subprocess

    read_port = 18766
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env.pop("XDG_CONFIG_HOME", None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve",
         "--http", "--port", str(read_port),
         "--token", "op-secret", "--read-token", "ro-secret"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE, text=True, env=env,
        cwd=str(PROJECT_ROOT),
    )

    def post(method: str, tok: str):
        req = urllib.request.Request(
            f"http://127.0.0.1:{read_port}/",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method}).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {tok}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, {}

    try:
        deadline = time.time() + 20
        code = None
        while time.time() < deadline:
            try:
                code, _ = post("app.version", "op-secret")
            except urllib.error.URLError:
                code = None
            if code == 200:
                break
            if proc.poll() is not None:
                err = proc.stderr.read() if proc.stderr else ""
                raise AssertionError(f"server exited early rc={proc.returncode}: {err}")
            time.sleep(0.3)
        assert code == 200, "server never came up"

        # reader may read
        code, body = post("app.version", "ro-secret")
        assert (code, body.get("result", {}).get("name")) == (200, "PkgForge")
        # reader must not mutate
        code, _ = post("settings.set", "ro-secret")
        assert code == 403
        # wrong operator token still rejected
        code, _ = post("app.version", "nope")
        assert code == 401
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_rate_limit_returns_429(http_server):
    codes = []
    for i in range(70):
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/",
            data=json.dumps({"jsonrpc": "2.0", "id": i,
                             "method": "app.version"}).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {TOKEN}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                codes.append(resp.status)
        except urllib.error.HTTPError as e:
            codes.append(e.code)
    assert 429 in codes
