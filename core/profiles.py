"""PkgForge — Multi-profile management (C2).

Profiles are named settings/history namespaces. The active profile rebinds
where settings.json / history.db live (see config.profile_config_dir).
"default" maps to the base CONFIG_DIR itself, so existing installs keep their
data without migration; named profiles live under CONFIG_DIR/profiles/<name>/.
"""

from __future__ import annotations

import shutil
from typing import Any

from config import (
    DEFAULT_PROFILE,
    PROFILE_NAME_RE,
    active_profile_file,
    get_active_profile,
    profiles_dir,
)
from i18n import tr


class ProfileError(ValueError):
    """Raised for invalid or forbidden profile operations."""


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not PROFILE_NAME_RE.match(name):
        raise ProfileError(
            "Geçersiz profil adı: harf, rakam, - veya _ (en fazla 64 karakter)"
        )


def list_profiles() -> list[dict[str, Any]]:
    """List every profile with its active flag (default always present)."""
    names: set[str] = {DEFAULT_PROFILE}
    root = profiles_dir()
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and PROFILE_NAME_RE.match(entry.name):
                names.add(entry.name)
    active = current_profile()
    return [{"name": n, "active": n == active} for n in sorted(names)]


def current_profile() -> str:
    """Return the name of the active profile."""
    return get_active_profile()


def create_profile(name: str) -> dict[str, Any]:
    """Create an empty profile directory with a blank settings.json."""
    _validate_name(name)
    target = profiles_dir() / name
    if name == DEFAULT_PROFILE or target.exists():
        raise ProfileError(f"Profil zaten mevcut: {name}")
    target.mkdir(parents=True)
    (target / "settings.json").write_text("{}", encoding="utf-8")
    return {"name": name}


def switch_profile(name: str) -> dict[str, Any]:
    """Make *name* the active profile (settings/history follow on next access)."""
    _validate_name(name)
    if name != DEFAULT_PROFILE and not (profiles_dir() / name).is_dir():
        raise ProfileError(tr("profiles.profil_bulunamadi_name_2", name=name))
    marker = active_profile_file()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(name, encoding="utf-8")
    return {"name": name}


def delete_profile(name: str) -> dict[str, Any]:
    """Delete a non-default, non-active profile and all of its data."""
    _validate_name(name)
    if name == DEFAULT_PROFILE:
        raise ProfileError("Varsayılan profil silinemez")
    if name == current_profile():
        raise ProfileError("Etkin profil silinemez; önce başka bir profile geçin")
    target = profiles_dir() / name
    if not target.is_dir():
        raise ProfileError(tr("profiles.profil_bulunamadi_name", name=name))
    shutil.rmtree(target)
    return {"name": name}
