"""Faz 4 (F4.10) - single source of truth for the release version."""
from __future__ import annotations

import json
from pathlib import Path

from config import APP_VERSION

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _desktop_json(name):
    return json.loads(
        (PROJECT_ROOT / "desktop" / name).read_text(encoding="utf-8"))


def test_core_version_matches_tauri_conf():
    conf = _desktop_json("src-tauri/tauri.conf.json")
    assert APP_VERSION == conf["version"]


def test_core_version_matches_package_json():
    pkg = _desktop_json("package.json")
    assert APP_VERSION == pkg["version"]
