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


# --- B1: aur.* --------------------------------------------------------------

def test_aur_search_starts(sidecar):
    resp = _rpc(sidecar, "aur.search", {"query": "firefox"})
    assert "result" in resp
    assert resp["result"].get("started") is True


def test_aur_info_invalid_name(sidecar):
    resp = _rpc(sidecar, "aur.info", {"name": "bad;rm -rf /"})
    assert "error" in resp
    assert resp["error"]["code"] == -32000


def test_aur_build_invalid_name(sidecar):
    resp = _rpc(sidecar, "aur.build", {"name": "../escape"})
    assert "error" in resp
    assert resp["error"]["code"] == -32000


# --- B4: security.cve_scan --------------------------------------------------

def test_cve_scan_bad_path(sidecar):
    resp = _rpc(sidecar, "security.cve_scan", {"pkg_path": "/nonexistent/x.pkg.tar.zst"})
    assert "error" in resp
    assert resp["error"]["code"] == -32000


# --- B6: queue.* ------------------------------------------------------------

def test_queue_add_and_list(sidecar, tmp_path):
    f = tmp_path / "test_1.0_amd64.deb"
    f.write_bytes(b"fake")
    resp = _rpc(sidecar, "queue.add", {"paths": [str(f)]})
    assert resp["result"]["added"] == 1
    resp2 = _rpc(sidecar, "queue.list")
    assert isinstance(resp2["result"], list)
    assert len(resp2["result"]) == 1
    assert resp2["result"][0]["status"] == "pending"


def test_queue_add_skips_missing(sidecar):
    resp = _rpc(sidecar, "queue.add", {"paths": ["/nonexistent/x.deb"]})
    assert resp["result"]["added"] == 0


def test_queue_priority_and_remove(sidecar, tmp_path):
    f = tmp_path / "p_1.0_amd64.deb"
    f.write_bytes(b"fake")
    _rpc(sidecar, "queue.add", {"paths": [str(f)]})
    items = _rpc(sidecar, "queue.list")["result"]
    item_id = items[0]["id"]
    resp = _rpc(sidecar, "queue.priority", {"id": item_id, "priority": 5})
    assert resp["result"]["ok"] is True
    items2 = _rpc(sidecar, "queue.list")["result"]
    assert items2[0]["priority"] == 5
    resp2 = _rpc(sidecar, "queue.remove", {"id": item_id})
    assert resp2["result"]["ok"] is True
    assert _rpc(sidecar, "queue.list")["result"] == []


def test_queue_start_no_pending(sidecar):
    resp = _rpc(sidecar, "queue.start")
    assert resp["result"]["started"] is False


# --- B3: schedule.* ---------------------------------------------------------

def test_schedule_get_defaults(sidecar):
    resp = _rpc(sidecar, "schedule.get")
    r = resp["result"]
    assert r["enabled"] is False
    assert r["interval_hours"] == 24
    assert r["task"] == "check_updates"


def test_schedule_set_and_get(sidecar):
    resp = _rpc(sidecar, "schedule.set", {"enabled": True, "interval_hours": 6})
    assert resp["result"]["ok"] is True
    r = _rpc(sidecar, "schedule.get")["result"]
    assert r["enabled"] is True
    assert r["interval_hours"] == 6
    assert r["next_run"] != ""
