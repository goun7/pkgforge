"""PkgForge - single source of truth for authorization data (F5.1).

HTTP reader scopes, polkit actions and their metadata are declared here
once. api_server, dbus_service and privileged all consume this module, so
the three enforcement surfaces cannot drift apart.

Regenerate the human-readable artifact with:
    python -m core.capabilities --emit > capabilities.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CAPABILITIES = {
    "http": {
        "reader": [
            "app.version",
            "tools.status",
            "settings.get",
            "history.list",
            "schedule.get",
            "profile.list",
            "profile.current",
            "queue.list",
            "plugin.list",
            "plugin.available",
            "plugin.audit",
            "dbus.status",
        ],
    },
    "polkit": {
        "helper_system_path": "/usr/share/pkgforge/scripts/install_helper.sh",
        "privileged_helper_system_path":
            "/usr/share/pkgforge/scripts/pkgforge-privileged.sh",
        "actions": [
            [
                "org.pkgforge.install",
                "PkgForge paket kurulumu",
                "Donusturulen paketi pacman ile kurmak icin yetkilendirme",
            ],
            [
                "org.pkgforge.delta-update",
                "PkgForge delta otomatik guncelleme",
                "Delta updater servis dosyalarini yazmak icin yetkilendirme",
            ],
            [
                "org.pkgforge.snapshot-cleanup",
                "PkgForge snapshot temizligi",
                "Zamanlanmis snapshot temizlik servisini yonetmek icin yetkilendirme",
            ],
        ],
        # F5.4: her polkit aksiyonunun yetkilendirdigi calistirilabilir dosya.
        # install hâlâ install_helper.sh kullanir; delta/snapshot ise konsolide
        # pkgforge-privileged.sh alt-komutlarina gecirildi.
        "action_exec_path": {
            "org.pkgforge.install":
                "/usr/share/pkgforge/scripts/install_helper.sh",
            "org.pkgforge.delta-update":
                "/usr/share/pkgforge/scripts/pkgforge-privileged.sh",
            "org.pkgforge.snapshot-cleanup":
                "/usr/share/pkgforge/scripts/pkgforge-privileged.sh",
        },
    },
}

_ARTIFACT = Path(__file__).resolve().parent.parent / "capabilities.json"


def http_reader_methods() -> frozenset:
    """Methods callable with the read-only HTTP token."""
    http = CAPABILITIES["http"]
    assert isinstance(http, dict)
    return frozenset(http["reader"])


def polkit_actions() -> list[tuple[str, str, str]]:
    """(action_id, title, description) triples for policy generation."""
    raw = CAPABILITIES["polkit"]
    actions: list = raw.get("actions", []) if isinstance(raw, dict) else []
    return [tuple(a) for a in actions]  # type: ignore[misc]


def helper_system_path() -> str:
    polkit = CAPABILITIES["polkit"]
    assert isinstance(polkit, dict)
    return str(polkit["helper_system_path"])


def privileged_helper_system_path() -> str:
    polkit = CAPABILITIES["polkit"]
    assert isinstance(polkit, dict)
    return str(polkit["privileged_helper_system_path"])


def action_exec_path(action_id: str) -> str:
    """Executable a polkit action authorizes (F5.4 per-action exec.path)."""
    polkit = CAPABILITIES["polkit"]
    assert isinstance(polkit, dict)
    mapping = polkit.get("action_exec_path", {})
    assert isinstance(mapping, dict)
    return str(mapping.get(action_id, polkit["helper_system_path"]))


def artifact_matches() -> bool:
    """True when the emitted JSON artifact equals the module state."""
    if not _ARTIFACT.is_file():
        return False
    try:
        return json.loads(_ARTIFACT.read_text(encoding="utf-8")) == CAPABILITIES
    except (json.JSONDecodeError, OSError):
        return False


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--emit":
        dest = Path(argv[1]) if len(argv) > 1 else _ARTIFACT
        dest.write_text(json.dumps(CAPABILITIES, indent=2) + chr(10),
                        encoding="utf-8")
        print("yazildi:", dest)
    else:
        print("kullanim: python -m core.capabilities --emit [dosya]")