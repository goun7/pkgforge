"""Faz 5 (F5.22) — pkgforge doctor: tek seferlik sistem teshisi.

Surum, harici araclar, anahtarlik, depolama, D-Bus ve zamanlayici sagligini
tek yapilandirilmis raporda toplar. Her proba best-effort'tur ve bozuk bir
alt-sistemde asla crash etmez; eksikligi raporlar.

Zorunlu araclarin yoklugu raporu 'ok=False' yapar; anahtarlik/D-Bus gibi
opsiyonel yetenekler yalnizca bilgi olarak isaretlenir (ozellik zarif duser).
"""
from __future__ import annotations

from typing import Any

from config import (
    APP_VERSION,
    CONFIG_DIR,
    discover_tools,
    get_active_profile,
    history_db_path,
    queue_db_path,
)
from i18n import tr


def _check_tools() -> dict[str, Any]:
    tools = discover_tools()
    missing_req = tools.missing_required
    return {
        "ok": not missing_req,
        "missing_required": missing_req,
        "missing_optional": tools.missing_optional,
        "debtap": bool(tools.debtap),
        "pkexec": bool(tools.pkexec),
        "distrobox": tools.has_distrobox,
    }


def _check_polkit() -> dict[str, Any]:
    """Faz 14: sudo/pkexec deneyimi teşhisi.

    Policy kurulu değilse pkexec HER çağrıda parola ister (genel fallback);
    kaynak ağacından çalıştırma da polkit'i her seferinde doğrulamaya zorlar.
    Bu prob, 'bolca sudo isteği' belirtisini görünür kök nedenine bağlar.
    """
    from pathlib import Path

    from core.privileged import POLKIT_EXEC_PATH_KEY, PRIVILEGED_HELPER

    actions = Path("/usr/share/polkit-1/actions")
    helper_policy = actions / "org.pkgforge.helper.policy"
    policy_installed = helper_policy.is_file()
    helper_in_system = Path(
        "/usr/share/pkgforge/scripts/pkgforge-privileged.sh").is_file()
    running_from_source = not str(PRIVILEGED_HELPER).startswith(
        "/usr/share/pkgforge/")

    detail = ""
    exec_path_ok = False
    if policy_installed:
        try:
            policy_text = helper_policy.read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            policy_text = ""
        exec_path_ok = POLKIT_EXEC_PATH_KEY in policy_text

    if not policy_installed:
        detail = tr("doctor.polkit_policy_yok")
    elif not exec_path_ok:
        detail = tr("doctor.polkit_exec_path_yok",
                    polkit_key=POLKIT_EXEC_PATH_KEY)
    elif running_from_source:
        detail = tr("doctor.polkit_kaynaktan")
    elif not helper_in_system:
        detail = tr("doctor.polkit_helper_yok")

    return {
        "ok": (policy_installed and helper_in_system
               and not running_from_source and exec_path_ok),
        "policy_installed": policy_installed,
        "exec_path_pinned": exec_path_ok,
        "helper_installed": helper_in_system,
        "running_from_source": running_from_source,
        "detail": detail,
    }


def _check_keyring() -> dict[str, Any]:
    try:
        from core.secrets_store import available

        ok = bool(available())
        return {
            "ok": ok,
            "detail": tr("doctor.keyring_ok" if ok else "doctor.keyring_yok"),
        }
    except Exception as exc:  # noqa: BLE001 - probe must not raise
        return {"ok": False, "detail": f"anahtarlik sorgulanamadi: {exc}"}


def _check_storage() -> dict[str, Any]:
    hist = history_db_path()
    qdb = queue_db_path()
    return {
        "ok": True,
        "config_dir": str(CONFIG_DIR),
        "config_dir_exists": CONFIG_DIR.is_dir(),
        "profile": get_active_profile(),
        "history_db": str(hist),
        "history_db_exists": hist.is_file(),
        "queue_db": str(qdb),
        "queue_db_exists": qdb.is_file(),
    }


def _check_dbus() -> dict[str, Any]:
    try:
        from core.dbus_service import service_status

        st = service_status()
        return {"ok": bool(st.get("available", False)), "detail": st}
    except Exception as exc:  # noqa: BLE001 - probe must not raise
        return {"ok": False, "detail": f"dbus durumu okunamadi: {exc}"}


def _check_scheduler() -> dict[str, Any]:
    try:
        from core.scheduler import TASKS, state

        return {"ok": True, "tasks": len(TASKS), "state": state()}
    except Exception as exc:  # noqa: BLE001 - probe must not raise
        return {"ok": False, "detail": f"zamanlayici okunamadi: {exc}"}


def run_doctor() -> dict[str, Any]:
    """Build the full diagnostic report. Never raises."""
    report: dict[str, Any] = {
        "version": APP_VERSION,
        "tools": _check_tools(),
        "polkit": _check_polkit(),
        "keyring": _check_keyring(),
        "storage": _check_storage(),
        "dbus": _check_dbus(),
        "scheduler": _check_scheduler(),
    }
    # Overall health is gated on required tools only; optional capabilities
    # (keyring/dbus) degrade gracefully and do not fail the report.
    report["ok"] = bool(report["tools"]["ok"])
    return report
