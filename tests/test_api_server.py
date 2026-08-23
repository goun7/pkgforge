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


class _LineReader:
    """Background reader pushing stdout lines into a queue.

    select() is unreliable on the buffered TextIOWrapper (data can sit in
    Python's internal buffer while select reports not-ready), so a plain
    blocking readline on a daemon thread is used instead.
    """

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


def _read_events(proc, timeout=30.0):
    """Read event lines (no id) until event.finished arrives."""
    import time

    reader = _LineReader(proc.stdout)
    events = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = reader.next_line(timeout=0.5)
        if line is None:
            break
        if not line:
            continue
        data = json.loads(line)
        if "id" not in data and data.get("method", "").startswith("event/"):
            events.append(data)
            if data["method"] == "event/finished":
                break
    return events


def test_pipeline_start_invalid_path(sidecar):
    resp = _rpc(sidecar, "pipeline.start", {"path": "/nonexistent/x.deb"})
    assert "error" in resp
    # Must be a handler error (-32000), NOT "method not found" (-32601)
    assert resp["error"]["code"] == -32000


def test_pipeline_start_real_deb(sidecar, tmp_path):
    # minimal fake .deb (ar archive) — pipeline fails at the analysis step
    # (malformed archive) and must still emit event.finished, never hang.
    # (A real .deb would reach compatibility_ready; that path is covered
    # by tests/test_pipeline_error_decision.py against the core directly.)
    deb = tmp_path / "fake_1.0_amd64.deb"
    deb.write_bytes(b"!<arch>\n" + b"0" * 64)
    resp = _rpc(sidecar, "pipeline.start", {"path": str(deb)})
    assert resp["result"]["started"] is True
    events = _read_events(sidecar, timeout=60)
    methods = [e["method"] for e in events]
    assert "event/finished" in methods
    fin = [e for e in events if e["method"] == "event/finished"][0]
    assert fin["params"]["success"] is False


def test_history_list_empty(sidecar):
    resp = _rpc(sidecar, "history.list")
    assert resp["result"] == []


def test_history_uninstall_invalid_name(sidecar):
    resp = _rpc(sidecar, "history.uninstall", {"name": "bad;rm -rf /"})
    assert "error" in resp
    assert resp["error"]["code"] == -32000


def test_history_rollback_no_backup(sidecar):
    resp = _rpc(sidecar, "history.rollback", {"name": "nonexistent-pkg"})
    assert "error" in resp
    assert resp["error"]["code"] == -32000


def test_history_clear(sidecar):
    resp = _rpc(sidecar, "history.clear")
    assert resp["result"]["ok"] is True
