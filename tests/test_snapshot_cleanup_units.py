"""Coverage itmesi — core/snapshot_cleanup.py servis kurulum/kaldirma."""
from __future__ import annotations

from types import SimpleNamespace

import core.snapshot_cleanup as SC


def _ns(code, out=""):
    return SimpleNamespace(returncode=code, stdout=out, stderr="")


def test_generate_script_contains_age_and_backends():
    s = SC._generate_cleanup_script(7)
    assert "MAX_AGE_DAYS=7" in s and "btrfs" in s and "zfs" in s


def test_generate_timer_unit_oncalendar():
    t = SC._generate_timer_unit(3)
    assert "OnCalendar=" in t and "3 days" in t


def test_install_requires_backend(monkeypatch):
    monkeypatch.setattr(SC, "detect_backend", lambda: "none")
    ok, msg = SC.install_cleanup_service(max_age_days=7)
    assert ok is False and "algılanmadı" in msg


def test_install_requires_systemctl(monkeypatch):
    monkeypatch.setattr(SC, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(SC.os.path, "isfile", lambda p: False)
    ok, msg = SC.install_cleanup_service()
    assert ok is False and "systemctl bulunamadı" in msg


def test_install_success_flow(monkeypatch):
    monkeypatch.setattr(SC, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(SC.os.path, "isfile", lambda p: True)
    writes = []

    def fake_run(argv, timeout=None, input=None, **kw):
        writes.append((list(argv), input))
        return _ns(0)
    monkeypatch.setattr(SC, "safe_run", fake_run)
    ok, msg = SC.install_cleanup_service(max_age_days=5)
    assert ok is True and "kuruldu" in msg
    scripts = [inp for argv, inp in writes if inp]
    assert any("MAX_AGE_DAYS=5" in s for s in scripts)


def test_install_pkexec_reject(monkeypatch):
    monkeypatch.setattr(SC, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(SC.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(SC, "safe_run",
                        lambda argv, timeout=None, input=None, **kw: _ns(1))
    ok, msg = SC.install_cleanup_service()
    assert ok is False and "yazılamadı" in msg


def test_remove_success_and_no_systemctl(monkeypatch):
    monkeypatch.setattr(SC.os.path, "isfile", lambda p: False)
    ok, msg = SC.remove_cleanup_service()
    assert ok is False and "systemctl bulunamadı" in msg

    monkeypatch.setattr(SC.os.path, "isfile", lambda p: True)
    seen = []

    def fake_run(argv, timeout=None, **kw):
        seen.append(list(argv))
        return _ns(0)
    monkeypatch.setattr(SC, "safe_run", fake_run)
    ok2, msg2 = SC.remove_cleanup_service()
    assert ok2 is True and "kaldırıldı" in msg2
    assert any("daemon-reload" in c for c in seen)


def _patch_status_queries(monkeypatch, enabled_code, active_code, show_out):
    def fake_run(argv, timeout=None, **kw):
        op = argv[1] if len(argv) > 1 else ""
        if op == "is-enabled":
            return _ns(enabled_code)
        if op == "is-active":
            return _ns(active_code)
        if op == "show":
            return _ns(0, out=show_out)
        return _ns(0)
    monkeypatch.setattr(SC, "safe_run", fake_run)


def test_status_defaults_without_systemctl(monkeypatch):
    monkeypatch.setattr(SC.os.path, "isfile", lambda p: False)
    st = SC.get_cleanup_status()
    assert st == {"installed": False, "active": False,
                  "next_run": "", "last_run": ""}


def test_status_installed_active_with_next_run(monkeypatch):
    monkeypatch.setattr(SC.os.path, "isfile", lambda p: True)
    _patch_status_queries(monkeypatch, 0, 0,
                          "NextElapseUSecRealtime=yarin 03:00")
    st = SC.get_cleanup_status()
    assert st["installed"] is True and st["active"] is True
    assert st["next_run"] == "yarin 03:00"


def test_status_enabled_but_inactive(monkeypatch):
    monkeypatch.setattr(SC.os.path, "isfile", lambda p: True)
    _patch_status_queries(monkeypatch, 0, 1, "")
    st = SC.get_cleanup_status()
    assert st["installed"] is True and st["active"] is False
