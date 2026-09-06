"""Faz 5 (F5.2b) — HTTP LAN hardening: insecure opt-in + trusted proxy XFF."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import core.api_server as A

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORT = 18773


# --- startup gates (raise before any server work, safe to call directly) ----

def test_nonloopback_without_token_refused():
    with pytest.raises(ValueError, match="--token"):
        A.serve_http(host="0.0.0.0", token="")


def test_nonloopback_token_but_no_insecure_flag_refused():
    with pytest.raises(ValueError, match="--insecure-http-lan"):
        A.serve_http(host="0.0.0.0", token="secret")


def test_nonloopback_insecure_flag_passes_gate(monkeypatch):
    # Past both gates the function would start a real server; stop it right
    # there with a sentinel to prove the gates themselves were satisfied.
    class _Sentinel(Exception):
        pass

    monkeypatch.setattr(A.transport, "_ensure_qapp", lambda: (_ for _ in ()).throw(_Sentinel()))
    with pytest.raises(_Sentinel):
        A.serve_http(host="0.0.0.0", token="secret", insecure_http_lan=True)


def test_loopback_needs_no_insecure_flag(monkeypatch):
    class _Sentinel(Exception):
        pass

    monkeypatch.setattr(A.transport, "_ensure_qapp", lambda: (_ for _ in ()).throw(_Sentinel()))
    # loopback + token must clear both gates (reach server bootstrap)
    with pytest.raises(_Sentinel):
        A.serve_http(host="127.0.0.1", token="secret")


# --- pure client-IP resolution ---------------------------------------------

def test_xff_ignored_without_trusted_proxy():
    assert A._resolve_client_ip("10.0.0.5", "1.2.3.4", False) == "10.0.0.5"


def test_xff_used_with_trusted_proxy():
    assert A._resolve_client_ip("10.0.0.5", "1.2.3.4", True) == "1.2.3.4"


def test_xff_first_hop_wins():
    assert A._resolve_client_ip("10.0.0.5", "9.9.9.9, 8.8.8.8", True) == "9.9.9.9"


def test_xff_empty_falls_back_to_socket():
    assert A._resolve_client_ip("10.0.0.5", "", True) == "10.0.0.5"
    assert A._resolve_client_ip("10.0.0.5", "   ", True) == "10.0.0.5"


# --- live smoke: trusted proxy flag is accepted end-to-end ------------------

def _post(token, headers=None):
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": "app.version", "params": {}}).encode()
    hdrs = {"Content-Type": "application/json",
            "Authorization": f"Bearer {token}"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/", data=body,
                                 method="POST", headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def test_trusted_proxy_server_accepts_xff():
    env = os.environ.copy()
    env["HOME"] = str(PROJECT_ROOT / ".tmp_home_hardening")
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve", "--http",
         "--port", str(PORT), "--host", "127.0.0.1", "--token", "tp",
         "--trusted-proxy"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        text=True, env=env, cwd=str(PROJECT_ROOT))
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
                break
            except OSError:
                if proc.poll() is not None:
                    raise RuntimeError("server died on startup")
                time.sleep(0.25)
        status, data = _post("tp", {"X-Forwarded-For": "203.0.113.7"})
        assert status == 200 and data["result"]["name"] == "PkgForge"
    finally:
        proc.terminate()
