"""Coverage itmesi — core/scheduler.py (durum/zamanlama/gorev/unit)."""
from __future__ import annotations

import time

import pytest

from core import scheduler as S


def test_state_defaults_in_isolated_home():
    st = S.state()
    assert st["enabled"] is False
    assert st["interval_hours"] == 24
    assert st["task"] == "check_updates"
    assert st["last_run"] == ""


def test_is_due_matrix():
    assert S.is_due({"enabled": False}) is False
    assert S.is_due({"enabled": True, "last_run": "",
                     "interval_hours": 1}) is True
    assert S.is_due({"enabled": True, "last_run": "kötü-biçim",
                     "interval_hours": 1}) is True
    now = time.time()
    recent = {"enabled": True, "interval_hours": 24,
              "last_run": time.strftime("%Y-%m-%d %H:%M:%S",
                                        time.localtime(now - 3600))}
    assert S.is_due(recent, now=now) is False
    old = dict(recent, last_run=time.strftime("%Y-%m-%d %H:%M:%S",
                                             time.localtime(now - 25 * 3600)))
    assert S.is_due(old, now=now) is True


def test_mark_ran_persists_stamp():
    stamp = S.mark_ran()
    assert S.state()["last_run"] == stamp


def test_run_task_unknown():
    out = S.run_task("yok_boyle_gorev")
    assert out["ok"] is False
    assert "Bilinmeyen" in out["detail"] and "check_updates" in out["detail"]


def test_run_task_backup_export_ok(monkeypatch):
    monkeypatch.setattr("core.cloud_sync.export_backup",
                        lambda output_path=None: {"path": "/tmp/x.zip"})
    out = S.run_task("backup_export")
    assert out["ok"] is True and out["path"] == "/tmp/x.zip"


def test_run_task_catches_exception(monkeypatch):
    def boom():
        raise RuntimeError("patladi")
    monkeypatch.setattr("core.upstream_tracker.check_all_installed_updates", boom)
    out = S.run_task("check_updates")
    assert out["ok"] is False and "patladi" in out["detail"]


def test_run_due_not_due_and_forced(monkeypatch):
    out = S.run_due(force=False)
    assert out["ran"] is False and "zamani gelmedi" in out["reason"]
    monkeypatch.setattr("core.upstream_tracker.check_all_installed_updates",
                        list)
    out2 = S.run_due(force=True)
    assert out2["ran"] is True and out2["task"] == "check_updates"
    assert out2["ok"] is True and out2["at"]


def test_service_unit_hardening_lines():
    t = S.service_unit_text()
    for needle in ("[Unit]", "[Service]", "Type=oneshot",
                   "NoNewPrivileges=true", "ProtectSystem=full",
                   "PrivateTmp=true", "-m main schedule-run"):
        assert needle in t, needle


def test_timer_unit_interval_clamp():
    low = S.timer_unit_text(0.5)
    assert "OnUnitActiveSec=3600s" in low
    normal = S.timer_unit_text(2)
    assert "OnUnitActiveSec=7200s" in normal
    assert "Unit=pkgforge.timer" in normal


def test_hours_guard():
    assert S.hours_guard("3") == 3.0
    assert S.hours_guard(1) == 1.0
    with pytest.raises(ValueError):
        S.hours_guard(0.5)


def test_install_timer_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(S.Path, "home", staticmethod(lambda: tmp_path))
    out = S.install_timer(interval_hours=6, dry_run=True)
    assert out == {"installed": False, "dry_run": True, "units": out["units"]}
    assert len(out["units"]) == 2


def test_install_timer_writes_units(tmp_path, monkeypatch):
    monkeypatch.setattr(S.Path, "home", staticmethod(lambda: tmp_path))
    out = S.install_timer(interval_hours=6, dry_run=False)
    assert out["installed"] is True
    base = tmp_path / ".config" / "systemd" / "user"
    assert (base / "pkgforge.service").is_file()
    assert (base / "pkgforge.timer").read_text(encoding="utf-8").count(
        "OnUnitActiveSec") == 1
