"""Faz 3 (C2) tests — multi-profile management."""
from __future__ import annotations

from pathlib import Path

import pytest

import config
import core.profiles as profiles
from core.history_db import HistoryDB
from core.profiles import ProfileError


@pytest.fixture
def cfg_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the whole profile machinery at an isolated temp root."""
    root = tmp_path / "pkgforge-config"
    root.mkdir()
    monkeypatch.setattr(config, "CONFIG_DIR", root)
    return root


def test_default_active_without_marker(cfg_root: Path):
    assert profiles.current_profile() == "default"
    assert profiles.list_profiles() == [{"name": "default", "active": True}]


def test_create_switch_list(cfg_root: Path):
    profiles.create_profile("work")
    listing = profiles.list_profiles()
    assert {"name": "default", "active": True} in listing
    assert {"name": "work", "active": False} in listing

    profiles.switch_profile("work")
    assert profiles.current_profile() == "work"
    assert profiles.list_profiles() == [
        {"name": "default", "active": False},
        {"name": "work", "active": True},
    ]


def test_settings_isolated_per_profile(cfg_root: Path):
    from i18n import load_settings, save_settings

    save_settings({"theme": "dark"})
    assert load_settings()["theme"] == "dark"

    profiles.create_profile("work")
    profiles.switch_profile("work")
    # New profile starts empty.
    assert load_settings() == {}
    save_settings({"theme": "light", "language": "en"})

    profiles.switch_profile("default")
    settings = load_settings()
    assert settings["theme"] == "dark"
    assert "language" not in settings


def test_history_db_follows_profile(cfg_root: Path):
    profiles.create_profile("work")
    profiles.switch_profile("work")
    db = HistoryDB()
    assert db.db_path == cfg_root / "profiles" / "work" / "history.db"

    profiles.switch_profile("default")
    db_default = HistoryDB()
    assert db_default.db_path == cfg_root / "history.db"


def test_explicit_db_path_still_wins(cfg_root: Path):
    custom = cfg_root / "custom.db"
    db = HistoryDB(db_path=custom)
    assert db.db_path == custom


def test_delete_rules(cfg_root: Path):
    with pytest.raises(ProfileError):
        profiles.delete_profile("default")

    profiles.create_profile("temp")
    profiles.switch_profile("temp")
    with pytest.raises(ProfileError):
        profiles.delete_profile("temp")  # active

    profiles.switch_profile("default")
    profiles.delete_profile("temp")
    names = [p["name"] for p in profiles.list_profiles()]
    assert "temp" not in names


def test_invalid_names_rejected(cfg_root: Path):
    for bad in ["../escape", "", "a/b", ".hidden", "x" * 65]:
        with pytest.raises(ProfileError):
            profiles.create_profile(bad)


def test_corrupt_marker_falls_back_to_default(cfg_root: Path):
    marker = cfg_root / "active_profile"
    marker.write_text("../../etc", encoding="utf-8")
    assert profiles.current_profile() == "default"
