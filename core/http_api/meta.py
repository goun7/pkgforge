"""Faz 5 (F5.11) — meta router: stateless app/system/ayarlar/polika handler'lari.

core/api_server.py bu modulu import edip METHODS sozlugune kaydeder. Handler'lar
stateless'tir (yalnizca core modullerini cagirir), bu yuzden guvenle tasinirlar.
"""
from __future__ import annotations

from typing import Any

from config import APP_NAME, APP_VERSION, discover_tools
from i18n import load_settings, save_settings


def handle_app_version(params: dict[str, Any]) -> dict[str, Any]:
    return {"name": APP_NAME, "version": APP_VERSION}


def handle_app_doctor(params: dict[str, Any]) -> dict[str, Any]:
    """F5.22: one-shot system diagnosis (read-only)."""
    from core.doctor import run_doctor

    return run_doctor()


def handle_tools_status(params: dict[str, Any]) -> dict[str, Any]:
    tools = discover_tools()
    return {
        "has_pacman": bool(tools.pacman),
        "has_makepkg": bool(tools.makepkg),
        "has_distrobox": bool(getattr(tools, "distrobox", None)),
        "missing_required": list(tools.missing_required),
        "missing_optional": list(tools.missing_optional),
    }


def handle_settings_get(params: dict[str, Any]) -> dict[str, Any]:
    return load_settings()


def handle_settings_set(params: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings()
    settings.update(params or {})
    save_settings(settings)
    return {"ok": True}


def handle_system_health(params: dict[str, Any]) -> dict[str, Any]:
    from core.history_db import HistoryDB

    db = HistoryDB()
    stats = db.get_usage_stats()
    total = stats["total"]
    by_status = stats["by_status"]
    installed = by_status.get("installed", 0)
    converted = by_status.get("converted", 0)
    failed = by_status.get("install_failed", 0)
    success_rate = ((installed + converted) / total * 100) if total > 0 else 0.0
    return {
        "total": total,
        "installed": installed,
        "converted": converted,
        "failed": failed,
        "success_rate": round(success_rate, 1),
        "by_type": stats["by_type"],
        "by_arch": stats["by_arch"],
        "url_count": stats["url_count"],
        "first_seen": stats["first_seen"],
        "last_seen": stats["last_seen"],
    }


def handle_stats_wrapped(params: dict[str, Any]) -> dict[str, Any]:
    """F5.24: annual conversion report (read-only)."""
    from core.stats_wrapped import build_wrapped

    year = params.get("year")
    return build_wrapped(year=int(year) if year else None)


def handle_policy_evaluate(params: dict[str, Any]) -> dict[str, Any]:
    """F5.19: evaluate a compatibility report against the active policy."""
    from core.policy_engine import evaluate

    return evaluate(params.get("report"))


def handle_policy_get(params: dict[str, Any]) -> dict[str, Any]:
    """F5.19: read the active compat policy level (read-only)."""
    from core.policy_engine import policy_from_settings

    return {"level": policy_from_settings().value}


def handle_policy_set(params: dict[str, Any]) -> dict[str, Any]:
    """F5.19: set the compat policy level (standard | strict)."""
    from core.policy_engine import SETTINGS_KEY, PolicyLevel

    raw = str(params.get("level", "")).lower().strip()
    try:
        lvl = PolicyLevel(raw)
    except ValueError:
        raise ValueError(
            f"Gecersiz politika seviyesi: {raw} (standard | strict)")
    settings = load_settings()
    settings[SETTINGS_KEY] = lvl.value
    save_settings(settings)
    return {"ok": True, "level": lvl.value}
