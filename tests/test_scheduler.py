"""Faz 4 (F4.6) — shared scheduler + systemd user timer."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core import scheduler

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _st(**kw):
    base = {"enabled": True, "interval_hours": 24.0,
            "task": "check_updates", "last_run": ""}
    base.update(kw)
    return base


def test_is_due_math():
    assert not scheduler.is_due(_st(enabled=False))
    assert scheduler.is_due(_st(last_run=""))
    now = time.time()
    recent = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 3600))
    stale = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 25 * 3600))
    assert not scheduler.is_due(_st(last_run=recent), now=now)
    assert scheduler.is_due(_st(last_run=stale), now=now)
    # corrupt timestamp -> treat as due
    assert scheduler.is_due(_st(last_run="not-a-date"), now=now)


def test_unit_texts_shape():
    svc = scheduler.service_unit_text()
    assert "[Service]" in svc and "Type=oneshot" in svc
    assert "ExecStart=" in svc and "-m main schedule-run" in svc
    # F5.3 sandbox hardening directives
    for directive in (
        "TimeoutStartSec=300",
        "NoNewPrivileges=true",
        "ProtectSystem=full",
        "PrivateTmp=true",
        "ReadWritePaths=%h/.config/pkgforge",
        "MemoryMax=1536M",
    ):
        assert directive in svc, directive
    tim = scheduler.timer_unit_text(2.0)
    assert "OnUnitActiveSec=7200s" in tim
    # timer points at the service unit (index-stable line)
    assert "Unit=pkgforge.timer" in tim
    assert "WantedBy=timers.target" in tim


def test_install_timer_real_writes_under_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    out = scheduler.install_timer(interval_hours=6, dry_run=False)
    assert out["installed"] is True
    svc = tmp_path / ".config/systemd/user/pkgforge.service"
    tim = tmp_path / ".config/systemd/user/pkgforge.timer"
    assert svc.is_file() and tim.is_file()
    assert "OnUnitActiveSec=21600s" in tim.read_text(encoding="utf-8")
    assert "systemctl --user" in out["enable"]


def test_install_timer_dry_run_touches_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    out = scheduler.install_timer(dry_run=True)
    assert out["installed"] is False and out["dry_run"] is True
    assert not (tmp_path / ".config/systemd/user").exists()
    assert any("pkgforge.timer" in p for p in out["units"])


def test_hours_guard_rejects_sub_hour():
    with pytest.raises(ValueError):
        scheduler.hours_guard(0.5)
    assert scheduler.hours_guard(1) == 1.0


def test_run_task_unknown_reports_known_set():
    out = scheduler.run_task("does_not_exist")
    assert out["ok"] is False and "check_updates" in out["detail"]


def test_cli_schedule_install_dry_run(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"),
         "schedule-install", "--dry-run"],
        capture_output=True, text=True, env=env, cwd=str(PROJECT_ROOT),
        timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr[-400:]
    assert "pkgforge.timer" in proc.stdout
    assert "dry-run" in proc.stdout
