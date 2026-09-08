"""PkgForge — Fleet console aggregation (Alan D / stratejik).

F5.18 fleet sync backends (webdav/git/rclone-s3 + age) ve F5.19 politika
motoru uzerine tek-cagri konsol agregasyonu. GUI'lar (Tauri Fleet sayfasi,
PyQt6 FleetDialog) bu ozeti tek `fleet.status` RPC'siyle ceker.
"""
from __future__ import annotations

import logging
import shutil
from typing import Any

log = logging.getLogger(__name__)


def get_fleet_status() -> dict[str, Any]:
    """Aggregate a fleet/enterprise console overview in a single call.

    Never raises: every external dependency (binaries, DB, settings) is
    guarded and falls back to a safe default so the console always renders.
    """
    from core.sync_backends import BACKENDS, age_available
    from i18n import load_settings

    try:
        settings = load_settings()
    except Exception:  # noqa: BLE001 - settings okunamazsa bos kabul et
        settings = {}

    sync_configured = bool(str(settings.get("sync_url", "")).strip())

    backends = {
        "webdav": {
            "configured": sync_configured,
            "available": True,  # webdav yerlesik (haric binary gerektirmez)
        },
        "git": {
            "configured": False,
            "available": shutil.which("git") is not None,
        },
        "rclone-s3": {
            "configured": False,
            "available": shutil.which("rclone") is not None,
        },
    }

    # Profiller (C2 coklu-profil)
    try:
        from core.cloud_sync import _profile_names
        profiles = _profile_names()
    except Exception:  # noqa: BLE001
        profiles = []

    # Gecmis kayit sayisi (node aktivite gostergesi)
    try:
        from core.history_db import HistoryDB
        history_count = len(HistoryDB().get_history(limit=100000))
    except Exception:  # noqa: BLE001
        history_count = 0

    # Aktif politika seviyesi (F5.19)
    try:
        from core.policy_engine import policy_from_settings
        policy_level = policy_from_settings(settings).name
    except Exception:  # noqa: BLE001
        policy_level = "STANDARD"

    return {
        "backends": backends,
        "backend_names": list(BACKENDS),
        "age_available": bool(age_available()),
        "profiles": profiles,
        "sync_configured": sync_configured,
        "history_count": history_count,
        "policy_level": policy_level,
    }
