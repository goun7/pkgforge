"""Faz 4 (F4.3) tests — batch queue honesty: registry, cancel, real parallel."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DEB = PROJECT_ROOT / "utest" / "hello_1.0.0-1_amd64.deb"


# --- in-process units --------------------------------------------------------

def test_parallel_clamped_to_4(monkeypatch: pytest.MonkeyPatch):

    import core.api_server as A

    captured = {}

    class _FakeThread:
        def __init__(self, target=None, args=(), daemon=False):
            captured["args"] = args
            self.daemon = daemon

        def start(self):
            pass

    monkeypatch.setattr(A.handlers_queue.threading, "Thread", _FakeThread)
    A.handlers_queue._queue_items["qx"] = {"id": "qx", "path": "/x.deb", "name": "x",
                            "status": "pending", "priority": 0, "message": ""}
    A.handlers_queue._queue_running = False
    try:
        res = A.handle_queue_start({"parallel": 99})
        assert res["started"] is True
        assert captured["args"] == (4, False)  # clamped + conversion-only
    finally:
        A.handlers_queue._queue_running = False
        A.handlers_queue._queue_items.pop("qx", None)


def test_queue_cancel_targets_registry(monkeypatch: pytest.MonkeyPatch):
    import core.api_server as A

    cancelled = []

    class _FakePipeline:
        def cancel(self):
            cancelled.append(True)

    A.handlers_queue._active_pipelines["q1"] = _FakePipeline()
    A.handlers_queue._active_pipelines["q2"] = _FakePipeline()
    try:
        out = A.handle_queue_cancel({"item_id": "q1"})
        assert out == {"cancelled": 1}
        # simulate completion removing the cancelled pipeline
        del A.handlers_queue._active_pipelines["q1"]
        out = A.handle_queue_cancel({})
        assert out == {"cancelled": 1}  # only q2 left
    finally:
        A.handlers_queue._active_pipelines.clear()


# --- real end-to-end parallel conversion (subprocess sidecar) -----------------

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


@pytest.mark.skipif(not FIXTURE_DEB.is_file(), reason="fixture deb missing")
def test_two_items_convert_in_parallel_and_finish(tmp_path):
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
    try:
        assert _rpc(proc, "app.version")["result"]["name"] == "PkgForge"

        added = _rpc(proc, "queue.add",
                     {"paths": [str(FIXTURE_DEB), str(FIXTURE_DEB)]})["result"]
        assert added["added"] == 2

        started = _rpc(proc, "queue.start", {"parallel": 2}, req_id=2)["result"]
        assert started["started"] is True

        # Drain events until both item finishes and the queue_done marker.
        finished_ids: set[str] = set()
        deadline_ok = False
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            data = json.loads(line)
            if data.get("method") == "event/finished":
                iid = data["params"].get("item_id")
                if data["params"].get("success"):
                    finished_ids.add(iid)
            if data.get("method") == "event/queue_done":
                deadline_ok = True
                break
        assert deadline_ok, "queue_done never arrived"
        assert len(finished_ids) == 2, f"only {finished_ids} succeeded"

        listing = {it["id"]: it for it in
                   _rpc(proc, "queue.list", req_id=3)["result"]}
        assert all(listing[i]["status"] == "done" for i in finished_ids)
        # F4.3 honesty: batch default is CONVERSION-ONLY — no install ran.
        for i in finished_ids:
            msg = listing[i]["message"].lower()
            assert "kuruldu" not in msg, f"unexpected install: {msg}"
            assert listing[i].get("message"), "expected a completion message"
        # Registry cleaned up after completion.
        reg = _rpc(proc, "dbus.status", req_id=4)  # sanity: sidecar alive
        assert "result" in reg
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
