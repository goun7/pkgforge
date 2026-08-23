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
