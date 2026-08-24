"""Faz 5 (F5.23) — SSE GET /events canli olay akisi."""
from __future__ import annotations

import http.client
import os
import queue
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import core.api_server as A

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORT = 18791


# --- in-process bus testleri ---------------------------------------------

def _reset_bus():
    with A._sse_lock:
        A._sse_history.clear()
        A._sse_subscribers.clear()


def test_publish_appends_to_history_and_notifies():
    _reset_bus()
    q = A._sse_subscribe()
    try:
        A._sse_publish("event/test", {"x": 1})
        with A._sse_lock:
            assert len(A._sse_history) == 1
        ev = q.get(timeout=1)
        assert ev["method"] == "event/test"
        assert ev["params"] == {"x": 1}
    finally:
        A._sse_unsubscribe(q)
        _reset_bus()


def test_event_in_http_mode_publishes_to_sse():
    _reset_bus()
    q = A._sse_subscribe()
    old = A._http_mode
    A._http_mode = True
    try:
        A._event("event/hello", {"msg": "hi"})
        ev = q.get(timeout=1)
        assert ev["method"] == "event/hello"
    finally:
        A._http_mode = old
        A._sse_unsubscribe(q)
        _reset_bus()


def test_unsubscribe_stops_delivery():
    _reset_bus()
    q = A._sse_subscribe()
    A._sse_unsubscribe(q)
    A._sse_publish("event/none", {})
    with pytest.raises(queue.Empty):
        q.get(timeout=0.2)
    _reset_bus()


def test_history_replay_order():
    _reset_bus()
    for i in range(3):
        A._sse_publish("event/n", {"i": i})
    with A._sse_lock:
        hist = list(A._sse_history)
    assert [h["params"]["i"] for h in hist] == [0, 1, 2]
    _reset_bus()


# --- canli HTTP sunucu testleri ------------------------------------------

@pytest.fixture
def http_server(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env.pop("XDG_CONFIG_HOME", None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve",
         "--http", "--port", str(PORT), "--token", "t"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, text=True, env=env,
        cwd=str(PROJECT_ROOT),
    )
    deadline = time.time() + 20
    up = False
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
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


def test_events_requires_auth(http_server):
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
    try:
        conn.request("GET", "/events")
        resp = conn.getresponse()
        assert resp.status == 401
        resp.read()
    finally:
        conn.close()


def test_events_streams_sse_with_token(http_server):
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
    try:
        conn.request("GET", "/events", headers={"Authorization": "Bearer t"})
        resp = conn.getresponse()
        assert resp.status == 200
        assert resp.getheader("Content-Type") == "text/event-stream"
        assert resp.getheader("Cache-Control") == "no-cache"
    finally:
        conn.close()
