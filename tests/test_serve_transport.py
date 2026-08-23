"""Faz 5 (F5.2a) - token-file/env support and rate-map pruning."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORT = 18772


def _post(path, token, req_id=1):
    body = json.dumps({"jsonrpc": "2.0", "id": req_id,
                       "method": "app.version", "params": {}}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def _start_server(env_extra):
    env = os.environ.copy()
    env["HOME"] = str(PROJECT_ROOT / ".tmp_home_transport")
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.update(env_extra)
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve", "--http",
         "--port", str(PORT), "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        text=True, env=env, cwd=str(PROJECT_ROOT))
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
            return proc
        except OSError:
            if proc.poll() is not None:
                raise RuntimeError("server died on startup")
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError("health never came up")


def test_token_from_file(tmp_path):
    tf = tmp_path / "tok"
    tf.write_text("filesecret\n", encoding="utf-8")
    proc = _start_server({})
    try:
        # --token-file is passed via argv; rebuild with it explicitly.
        proc.terminate()
        proc.wait(timeout=5)
        env = os.environ.copy()
        env["HOME"] = str(PROJECT_ROOT / ".tmp_home_transport")
        env["QT_QPA_PLATFORM"] = "offscreen"
        proc = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "main.py"), "serve", "--http",
             "--port", str(PORT), "--host", "127.0.0.1",
             "--token-file", str(tf)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            text=True, env=env, cwd=str(PROJECT_ROOT))
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
                break
            except OSError:
                time.sleep(0.25)
        status, _ = _post("/", "wrong")
        assert status == 401
        status, data = _post("/", "filesecret")
        assert status == 200 and data["result"]["name"] == "PkgForge"
    finally:
        proc.terminate()


def test_token_from_env(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    proc = _start_server({"PKGFORGE_TOKEN": "envsecret"})
    try:
        status, _ = _post("/", "nope")
        assert status == 401
        status, _data2 = _post("/", "envsecret")
        assert status == 200
    finally:
        proc.terminate()


def test_rate_map_prunes_stale_buckets():
    import core.api_server as A

    A._http_rate.clear()
    now = 1_000_000.0
    for i in range(5000):
        A._http_rate[f"10.0.0.{i}"] = deque()
    # Next call exceeds the 4096 threshold and sweeps empty buckets.
    assert A._rate_limited("9.9.9.9", now) is False
    assert len(A._http_rate) <= 2
    A._http_rate.clear()