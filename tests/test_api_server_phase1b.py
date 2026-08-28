"""Faz 1 (Alan A) sidecar handler tests — export/graph/source/system (F1.2).

Covers A1 (export centers), A3 (dep graph), A5 (from-source) and
A6 (system tools). Same subprocess fixture pattern as test_api_server.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
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


class _LineReader:
    """Queue-based stdout reader (select() is unreliable on buffered streams)."""

    def __init__(self, stream):
        import queue
        import threading

        self._q = queue.Queue()
        self._t = threading.Thread(target=self._run, args=(stream,), daemon=True)
        self._t.start()

    def _run(self, stream):
        for line in stream:
            self._q.put(line.rstrip())
        self._q.put(None)

    def next_line(self, timeout=0.5):
        import queue

        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return ""


def _read_until_event(proc, event_name, timeout=30.0):
    """Read lines until the named event arrives; return its params."""
    reader = _LineReader(proc.stdout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = reader.next_line(timeout=0.5)
        if line is None:
            break
        if not line:
            continue
        data = json.loads(line)
        if "id" not in data and data.get("method") == event_name:
            return data.get("params", {})
    raise TimeoutError(f"event {event_name} not received within {timeout}s")


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


# --- A3: graph.* ------------------------------------------------------------

def test_graph_build_nonexistent(sidecar):
    resp = _rpc(sidecar, "graph.build", {"pkg_path": "/nonexistent/x.pkg.tar.zst"})
    assert "error" in resp
    assert resp["error"]["code"] == -32000


# --- A6: system.* -----------------------------------------------------------

def test_system_health_empty_history(sidecar):
    resp = _rpc(sidecar, "system.health")
    assert "result" in resp
    r = resp["result"]
    assert r["total"] == 0
    assert "success_rate" in r
    assert "by_type" in r


def test_system_snapshot_status_returns_dict(sidecar):
    resp = _rpc(sidecar, "system.snapshot_status")
    assert "result" in resp
    assert isinstance(resp["result"], dict)


def test_system_snapshot_install_starts(sidecar):
    # Artik gercek kurulumu (pkexec) baslatir, hemen {"started": True} doner;
    # sonuc event/snapshot_done ile gelir. Test sisteminde Btrfs/ZFS yok,
    # detect_backend "none" doner ve kurulum yan-etkisiz erken biter.
    resp = _rpc(sidecar, "system.snapshot_install")
    assert resp["result"]["started"] is True


def test_system_snapshot_remove_starts(sidecar):
    resp = _rpc(sidecar, "system.snapshot_remove")
    assert resp["result"]["started"] is True


def test_system_verify_rollback_starts(sidecar):
    # threaded op: immediate ack, result arrives via event.system_done
    resp = _rpc(sidecar, "system.verify_rollback")
    assert resp["result"]["started"] is True


def test_system_benchmark_starts(sidecar):
    resp = _rpc(sidecar, "system.benchmark", {"quick": True})
    assert resp["result"]["started"] is True


# --- A1: export.* -----------------------------------------------------------

def test_export_flatpak_list_returns_list(sidecar):
    resp = _rpc(sidecar, "export.flatpak_list")
    assert "result" in resp
    assert isinstance(resp["result"], list)


def test_export_oci_nonexistent(sidecar):
    resp = _rpc(sidecar, "export.oci", {"pkg_path": "/nonexistent/x.pkg.tar.zst"})
    assert "error" in resp
    assert resp["error"]["code"] == -32000


def test_export_appimage_nonexistent(sidecar):
    resp = _rpc(sidecar, "export.appimage_to_deb", {"appimage_path": "/nonexistent/x.AppImage"})
    assert "error" in resp
    assert resp["error"]["code"] == -32000


# --- A5: source.* -----------------------------------------------------------

def test_source_generate_empty_url(sidecar):
    resp = _rpc(sidecar, "source.generate", {"repo_url": ""})
    assert "error" in resp
    assert resp["error"]["code"] == -32000


def test_source_generate_invalid_url_emits_failure(sidecar):
    resp = _rpc(sidecar, "source.generate", {"repo_url": "not-a-valid-url"})
    assert resp["result"]["started"] is True
    params = _read_until_event(sidecar, "event/source_done", timeout=60)
    assert params["ok"] is False
