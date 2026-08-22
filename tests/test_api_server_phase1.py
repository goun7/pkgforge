"""Faz 1 (Alan A) sidecar handler tests — security.* and delta.*.

These exercise the JSON-RPC surface added for A2 (security panel) and
A4 (delta updater). They follow the subprocess fixture pattern from
test_api_server.py: a real `main.py serve` sidecar, queue-based reader.
"""
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


# --- A2: security.* ---------------------------------------------------------

def test_security_verify_nonexistent_path(sidecar):
    resp = _rpc(sidecar, "security.verify", {"pkg_path": "/nonexistent/x.pkg.tar.zst"})
    assert "error" in resp
    # handler error, not "method not found"
    assert resp["error"]["code"] == -32000


def test_security_keys_returns_list(sidecar):
    resp = _rpc(sidecar, "security.keys")
    assert "result" in resp
    assert isinstance(resp["result"], list)


def test_security_sigstore_status_returns_dict(sidecar):
    resp = _rpc(sidecar, "security.sigstore_status")
    assert "result" in resp
    assert isinstance(resp["result"], dict)


def test_security_provenance_missing_returns_null(sidecar):
    resp = _rpc(sidecar, "security.provenance", {"pkg_path": "/nonexistent/x.pkg.tar.zst"})
    # No provenance found -> result is null (not an error)
    assert "result" in resp
    assert resp["result"] is None


# --- A4: delta.* ------------------------------------------------------------

def test_delta_status_returns_dict(sidecar):
    resp = _rpc(sidecar, "delta.status")
    assert "result" in resp
    assert isinstance(resp["result"], dict)
    # real shape from core.delta_updater.get_auto_update_status
    assert "installed" in resp["result"]
    assert "active" in resp["result"]
    assert "next_run" in resp["result"]


def test_delta_enable_requires_privilege(sidecar):
    resp = _rpc(sidecar, "delta.enable")
    assert "result" in resp
    assert resp["result"]["requires_privilege"] is True


def test_delta_disable_requires_privilege(sidecar):
    resp = _rpc(sidecar, "delta.disable")
    assert "result" in resp
    assert resp["result"]["requires_privilege"] is True
