"""JSON-RPC sidecar protocol tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _rpc(proc, method, params=None, req_id=1):
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    # read lines until we get our response id
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("sidecar closed stdout")
        data = json.loads(line)
        if data.get("id") == req_id:
            return data


@pytest.fixture
def sidecar(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env.pop("XDG_CONFIG_HOME", None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, env=env,
        cwd=str(PROJECT_ROOT),
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_app_version(sidecar):
    resp = _rpc(sidecar, "app.version")
    assert resp["result"]["name"] == "PkgForge"
    assert "version" in resp["result"]


def test_tools_status(sidecar):
    resp = _rpc(sidecar, "tools.status")
    assert "has_pacman" in resp["result"]


def test_settings_roundtrip(sidecar):
    r1 = _rpc(sidecar, "settings.get", req_id=1)
    assert isinstance(r1["result"], dict)
    r2 = _rpc(sidecar, "settings.set", {"theme": "light"}, req_id=2)
    assert r2["result"]["ok"] is True
    r3 = _rpc(sidecar, "settings.get", req_id=3)
    assert r3["result"]["theme"] == "light"


def test_unknown_method_returns_error(sidecar):
    resp = _rpc(sidecar, "no.such.method")
    assert "error" in resp
    assert resp["error"]["code"] == -32601
