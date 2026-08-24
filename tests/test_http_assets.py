"""Faz 5 (F5.5) — HTTP asset dosyalari: vendorored swagger, CSP, yol guvenligi."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from core import http_assets

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORT = 18774


# --- loader (birim) testleri ----------------------------------------------

def test_dashboard_html_has_csp_and_offline():
    html = http_assets.dashboard_html().decode("utf-8")
    assert "Content-Security-Policy" in html
    assert "default-src 'self'" in html
    # Panocu dis kaynakitari yok (offline):
    assert "unpkg.com" not in html
    assert "cdn" not in html.lower()


def test_docs_html_uses_vendored_swagger():
    html = http_assets.docs_html().decode("utf-8")
    assert "Content-Security-Policy" in html
    assert "/assets/swagger/swagger-ui.css" in html
    assert "/assets/swagger/swagger-ui-bundle.js" in html
    # CDN'e bagimlilik kalmadi:
    assert "unpkg.com" not in html


def test_swagger_assets_are_vendored_and_nonempty():
    assert len(http_assets.swagger_css()) > 10_000
    assert len(http_assets.swagger_bundle_js()) > 100_000
    assert http_assets.swagger_css().startswith(b".swagger-ui") or b".swagger-ui" in http_assets.swagger_css()[:200]


def test_read_asset_blocks_path_traversal():
    with pytest.raises(FileNotFoundError):
        http_assets.read_asset("../secrets.txt")
    with pytest.raises(FileNotFoundError):
        http_assets.read_asset("swagger/../../config.py")


# --- canli sunucu testleri -------------------------------------------

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


def _get(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=5) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def test_docs_served_with_csp_and_vendored_assets(http_server):
    status, ctype, body = _get("/docs")
    assert status == 200
    assert ctype.startswith("text/html")
    assert b"Content-Security-Policy" in body
    assert b"/assets/swagger/swagger-ui-bundle.js" in body


def test_dashboard_served_with_csp(http_server):
    status, ctype, body = _get("/")
    assert status == 200
    assert ctype.startswith("text/html")
    assert b"Content-Security-Policy" in body
    assert b"PkgForge Panosu" in body


def test_swagger_css_served(http_server):
    status, ctype, body = _get("/assets/swagger/swagger-ui.css")
    assert status == 200
    assert ctype.startswith("text/css")
    assert len(body) > 10_000


def test_swagger_bundle_served(http_server):
    status, ctype, body = _get("/assets/swagger/swagger-ui-bundle.js")
    assert status == 200
    assert ctype.startswith("application/javascript")
    assert len(body) > 100_000


def test_unknown_asset_404(http_server):
    with pytest.raises(urllib.error.HTTPError) as ei:
        _get("/assets/swagger/../../config.py")
    assert ei.value.code in (404, 400)
