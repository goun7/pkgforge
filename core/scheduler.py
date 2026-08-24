"""PkgForge - shared scheduler logic + systemd user timer (F4.6).

The GUI/daemon in-process tick and the headless entry points
("pkgforge schedule-run", "pkgforge schedule-install") share the same
state/due/run helpers so a systemd timer behaves identically to the app.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

SERVICE_UNIT = "pkgforge.service"
TIMER_UNIT = "pkgforge.timer"


def state() -> dict:
    from i18n import load_settings

    s = load_settings()
    return {
        "enabled": bool(s.get("schedule_enabled", False)),
        "interval_hours": float(s.get("schedule_interval_hours", 24)),
        "task": str(s.get("schedule_task", "check_updates")),
        "last_run": str(s.get("schedule_last_run", "")),
    }


def is_due(st: dict, now=None) -> bool:
    """True when the schedule should fire right now."""
    if not st.get("enabled"):
        return False
    if not st["last_run"]:
        return True
    try:
        last = time.mktime(time.strptime(st["last_run"], "%Y-%m-%d %H:%M:%S"))
    except (ValueError, OverflowError, OSError):
        return True
    current = time.time() if now is None else now
    return (current - last) >= st["interval_hours"] * 3600


def mark_ran() -> str:
    from i18n import load_settings, save_settings

    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    s = load_settings()
    s["schedule_last_run"] = stamp
    save_settings(s)
    return stamp


def _task_check_updates() -> dict:
    from core.upstream_tracker import check_all_installed_updates

    results = check_all_installed_updates()
    updates = [r for r in results if r.has_update]
    return {"ok": True, "detail": str(len(updates)) + " guncelleme bulundu"}


def _task_sync_push() -> dict:
    from core.cloud_sync import webdav_push

    return webdav_push()


def _task_backup_export() -> dict:
    from core.cloud_sync import export_backup

    return export_backup()


def _task_restore_drill() -> dict:
    from core.cloud_sync import restore_drill

    return restore_drill()


TASKS = {
    "check_updates": _task_check_updates,
    "sync_push": _task_sync_push,
    "backup_export": _task_backup_export,
    "restore_drill": _task_restore_drill,
}

KNOWN_TASKS = ", ".join(sorted(TASKS))


def run_task(task):
    fn = TASKS.get(task)
    if fn is None:
        return {"ok": False,
                "detail": "Bilinmeyen gorev: " + task + " (" + KNOWN_TASKS + ")"}
    try:
        out = fn()
        out.setdefault("ok", True)
        return out
    except Exception as exc:  # noqa: BLE001 - scheduled jobs must not crash
        return {"ok": False, "detail": str(exc)}


def run_due(force=False):
    st = state()
    if not force and not is_due(st):
        return {"ran": False, "reason": "zamani gelmedi"}
    at = mark_ran()
    result = run_task(st["task"])
    out = {"ran": True, "at": at, "task": st["task"]}
    out.update(result)
    return out


def service_unit_text() -> str:
    exe = Path(sys.executable)
    workdir = Path(__file__).resolve().parent.parent
    lines = [
        "[Unit]",
        "Description=PkgForge zamanlanmis gorev",
        "",
        "[Service]",
        "Type=oneshot",
        # F5.3: sandbox hardening. NoNewPrivileges intentionally blocks
        # pkexec — headless tasks are conversion/scan-only by design.
        "TimeoutStartSec=300",
        "NoNewPrivileges=true",
        "ProtectSystem=full",
        "PrivateTmp=true",
        "ReadWritePaths=%h/.config/pkgforge",
        "MemoryMax=1536M",
        "WorkingDirectory=" + str(workdir),
        "ExecStart=" + str(exe) + " -m main schedule-run",
        "",
    ]
    return chr(10).join(lines)


def timer_unit_text(interval_hours) -> str:
    secs = max(3600, int(float(interval_hours) * 3600))
    lines = [
        "[Unit]",
        "Description=PkgForge zamanlayici",
        "",
        "[Timer]",
        "OnBootSec=10min",
        "OnUnitActiveSec=" + str(secs) + "s",
        "Unit=" + TIMER_UNIT,
        "",
        "[Install]",
        "WantedBy=timers.target",
        "",
    ]
    return chr(10).join(lines)


def hours_guard(value):
    v = float(value)
    if v < 1:
        raise ValueError("Aralik en az 1 saat olmali")
    return v


def install_timer(interval_hours=None, dry_run=False):
    """Write user systemd units under HOME; dry_run returns paths+content."""
    st = state()
    raw = st["interval_hours"] if interval_hours is None else interval_hours
    hours = hours_guard(raw)
    base = Path.home() / ".config" / "systemd" / "user"
    real = {
        str(base / SERVICE_UNIT): service_unit_text(),
        str(base / TIMER_UNIT): timer_unit_text(hours),
    }
    if dry_run:
        return {"installed": False, "dry_run": True, "units": real}
    base.mkdir(parents=True, exist_ok=True)
    for path, text in real.items():
        tmp = Path(path + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    hint = ("systemctl --user daemon-reload && "
            "systemctl --user enable --now pkgforge.timer")
    return {"installed": True, "dry_run": False, "units": real, "enable": hint}
