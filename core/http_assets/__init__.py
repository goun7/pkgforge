"""Static HTTP assets served by the sidecar's built-in API server (F5.5).

Keeping these out of core/api_server.py shrinks that module and lets the
HTML/CSP evolve without touching Python. Files are read once and cached.
swagger-ui is vendored (Apache-2.0, see swagger/NOTICE) so /docs works
offline with no CDN dependency.
"""
from __future__ import annotations

from functools import cache
from pathlib import Path

_ASSET_DIR = Path(__file__).resolve().parent


@cache
def read_asset(name: str) -> bytes:
    """Return the raw bytes of a bundled asset (path-traversal safe)."""
    target = (_ASSET_DIR / name).resolve()
    if not target.is_relative_to(_ASSET_DIR.resolve()):
        raise FileNotFoundError(name)
    return target.read_bytes()


def dashboard_html() -> bytes:
    return read_asset("dashboard.html")


def docs_html() -> bytes:
    return read_asset("docs.html")


def swagger_css() -> bytes:
    return read_asset("swagger/swagger-ui.css")


def swagger_bundle_js() -> bytes:
    return read_asset("swagger/swagger-ui-bundle.js")
