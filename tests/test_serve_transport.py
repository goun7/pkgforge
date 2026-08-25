"""Faz 5 (F5.2a) - token-file/env support and rate-map pruning.

Titreklik notu: sabit port + wait'siz terminate, bir onceki sunucu olmeden
yenisinin ayni portu baglamasini (EADDRINUSE -> cocuk olur, /health'i eski
tokensiz sunucu cevaplari -> her istek 401) mümkun kiliyordu. Artik her test
kernel'in atadigi ozgun portu kullanir ve temizlik terminate+wait+kill
zinciriyle kesindir.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    """Kernel'den hic baglanmamis bir port al (0.0.0.0 degil, loopback)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _post(port: int, path: str, token: str, req_id: int = 1):
    body = json.dumps({"jsonrpc": "2.0", "id": req_id,
                       "method": "app.version", "params": {}}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def _stop(proc: subprocess.Popen) -> None:
    """Sunucuyu kesin durdur: terminate -> wait -> kill."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _start_server(env_extra: dict[str, str], extra_args: list[str] | None = None):
    port = _free_port()
    env = os.environ.copy()
    env["HOME"] = str(PROJECT_ROOT / ".tmp_home_transport")
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.update(env_extra)
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve", "--http",
         "--port", str(port), "--host", "127.0.0.1", *(extra_args or [])],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, env=env, cwd=str(PROJECT_ROOT))
    last_err: Exception | None = None
    for _ in range(60):
        if proc.poll() is not None:
            err = ""
            if proc.stderr:
                err = proc.stderr.read()[-2000:]
            raise RuntimeError(f"server died on startup:\n{err}")
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=2) as r:
                payload = json.loads(r.read())
            if payload.get("service") == "pkgforge-http":
                return proc, port
            # Baskasi cevapliyor: cocugu birakma, kanitla cok.
            _stop(proc)
            raise RuntimeError(f"yabanci surec /health cevapliyor: {payload}")
        except (OSError, ValueError) as exc:
            last_err = exc
            time.sleep(0.25)
    _stop(proc)
    raise RuntimeError(f"health never came up: {last_err}")


def test_token_from_file(tmp_path):
    tf = tmp_path / "tok"
    tf.write_text("filesecret\n", encoding="utf-8")
    proc, port = _start_server({}, extra_args=["--token-file", str(tf)])
    try:
        status, _ = _post(port, "/", "wrong")
        assert status == 401, f"yanlis token 401 beklenirdi: {status}"
        status, data = _post(port, "/", "filesecret")
        assert status == 200, f"dogru token reddedildi: {status} {data}"
        assert data["result"]["name"] == "PkgForge"
    finally:
        _stop(proc)


def test_token_from_env():
    proc, port = _start_server({"PKGFORGE_TOKEN": "envsecret"})
    try:
        status, _ = _post(port, "/", "nope")
        assert status == 401, f"yanlis token 401 beklenirdi: {status}"
        status, data = _post(port, "/", "envsecret")
        assert status == 200, f"dogru token reddedildi: {status} {data}"
    finally:
        _stop(proc)


def test_rate_map_prunes_stale_buckets():
    import core.api_server as A

    A._http_rate.clear()
    now = 1_000_000.0
    for i in range(5000):
        A._http_rate[f"10.0.0.{i}"] = deque()
    # Sonraki cagri 4096 esigini asar ve bos kovalari supler.
    assert A._rate_limited("9.9.9.9", now) is False
    assert len(A._http_rate) <= 2
    A._http_rate.clear()
