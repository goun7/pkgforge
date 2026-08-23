"""Faz 2 (Alan B) sidecar handler tests — plugin.* (B8) and compare.diff (B5)."""
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


# --- B8: plugin.* -----------------------------------------------------------

def test_plugin_list_returns_list(sidecar):
    resp = _rpc(sidecar, "plugin.list")
    assert "result" in resp
    assert isinstance(resp["result"], list)


def test_plugin_available_returns_list(sidecar):
    # may be empty when offline, but must be a list, not an error
    resp = _rpc(sidecar, "plugin.available")
    assert "result" in resp
    assert isinstance(resp["result"], list)


def test_plugin_uninstall_invalid_name(sidecar):
    resp = _rpc(sidecar, "plugin.uninstall", {"name": "bad;rm -rf /"})
    assert "error" in resp
    assert resp["error"]["code"] == -32000


def test_plugin_audit_returns_list(sidecar):
    resp = _rpc(sidecar, "plugin.audit")
    assert "result" in resp
    assert isinstance(resp["result"], list)


# --- B5: compare.diff -------------------------------------------------------

def test_compare_diff_missing_files(sidecar):
    resp = _rpc(sidecar, "compare.diff",
                {"old_path": "/nonexistent/a.pkg.tar.zst", "new_path": "/nonexistent/b.pkg.tar.zst"})
    assert "error" in resp
    assert resp["error"]["code"] == -32000
