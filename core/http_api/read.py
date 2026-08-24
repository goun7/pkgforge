"""Faz 5 (F5.11) — read router: stateless read-only JSON-RPC handler'lari.

Yalnizca core modullerini cagiran, global durum tutmayan okuma handler'lari.
core/api_server.py bunlari import edip METHODS'a kaydeder (facade).
"""
from __future__ import annotations


def handle_history_list(params):
    from core.history_db import HistoryDB

    db = HistoryDB()
    records = db.get_history(limit=int(params.get("limit", 100)))
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "package_name": r.package_name,
            "package_type": r.package_type,
            "status": r.status,
            "original_file": r.original_file,
            "source_url": r.source_url or "",
        }
        for r in records
    ]


def handle_plugin_list(params):
    from core.plugins.marketplace import list_installed_plugins

    return list_installed_plugins()


def handle_plugin_available(params):
    from core.plugins.marketplace import fetch_available_plugins

    offline = bool(params.get("offline", False))
    return fetch_available_plugins(offline=offline)


def handle_plugin_audit(params):
    from core.plugins.marketplace import audit_plugins

    return audit_plugins()


def handle_profile_list(params):
    from core.profiles import list_profiles

    return list_profiles()


def handle_profile_current(params):
    from core.profiles import current_profile

    return {"name": current_profile()}


def handle_dbus_status(params):
    from core.dbus_service import service_status

    return service_status()
