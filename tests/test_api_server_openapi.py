"""Faz 4 (F4.8/F4.9) - public OpenAPI, Swagger docs, dashboard shell."""
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORT = 18771


def _get(path):
    url = f"http://127.0.0.1:{PORT}{path}"
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read()


@pytest.fixture(scope="module")
def http_server():
    env = os.environ.copy()
    env["HOME"] = str(PROJECT_ROOT / ".tmp_home_openapi")
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve", "--http",
         "--port", str(PORT), "--token", "opsecret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        text=True, env=env, cwd=str(PROJECT_ROOT))
    base = f"http://127.0.0.1:{PORT}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/health", timeout=2)
            break
        except (OSError, urllib.error.URLError):
            if proc.poll() is not None:
                proc.kill()
                raise RuntimeError("server died on startup")
            time.sleep(0.25)
    else:
        proc.kill()
        raise RuntimeError("health never came up")
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_openapi_is_public_and_lists_all_methods(http_server):
    status, body = _get("/openapi.json")
    assert status == 200
    schema = json.loads(body)
    assert schema["openapi"].startswith("3.")
    from core.api_server import METHODS
    assert len(schema["paths"]) == len(METHODS)
    assert "/rpc/app.version" in schema["paths"]


def test_docs_page_public_html(http_server):
    status, body = _get("/docs")
    assert status == 200
    html = body.decode("utf-8")
    assert "swagger-ui" in html and "/openapi.json" in html


def test_dashboard_shell_public_and_functional(http_server):
    status, body = _get("/")
    assert status == 200
    html = body.decode("utf-8")
    assert "PkgForge Panosu" in html
    assert "/openapi.json" in html and "Bearer" in html


def test_unknown_path_still_404(http_server):
    raised = False
    try:
        _get("/nope")
    except urllib.error.HTTPError as e:
        raised = e.code == 404
    assert raised