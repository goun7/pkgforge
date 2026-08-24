"""Faz 5 (F5.22) — pkgforge doctor teshis komutu."""
from __future__ import annotations

import argparse

import core.doctor as DOC


def test_run_doctor_structure_expected_sections():
    r = DOC.run_doctor()
    for key in ("version", "tools", "keyring", "storage", "dbus",
                "scheduler", "ok"):
        assert key in r
    assert isinstance(r["ok"], bool)
    assert isinstance(r["tools"]["missing_required"], list)


def test_doctor_ok_gated_on_required_tools(monkeypatch):
    class _Fake:
        missing_required = ["pacman"]  # noqa: RUF012 - test fake
        missing_optional = []  # noqa: RUF012 - test fake
        debtap = ""
        pkexec = ""
        has_distrobox = False

    monkeypatch.setattr(DOC, "discover_tools", lambda: _Fake())
    r = DOC.run_doctor()
    assert r["ok"] is False
    assert r["tools"]["missing_required"] == ["pacman"]


def test_doctor_never_raises_on_keyring_failure(monkeypatch):
    import core.secrets_store as SS

    def _boom():
        raise RuntimeError("dbus kapali")

    monkeypatch.setattr(SS, "available", _boom)
    r = DOC.run_doctor()
    assert r["keyring"]["ok"] is False
    assert "sorgulanamadi" in r["keyring"]["detail"]


def test_rpc_app_doctor_returns_report():
    import core.api_server as A

    out = A.handle_app_doctor({})
    assert "version" in out and "tools" in out and "ok" in out


def _healthy_report():
    return {
        "version": "2.0.0",
        "tools": {"ok": True, "missing_required": [], "missing_optional": [],
                  "debtap": True, "pkexec": True, "distrobox": False},
        "keyring": {"ok": False, "detail": "yok"},
        "storage": {"ok": True, "profile": "default", "config_dir": "/x",
                    "history_db_exists": True, "queue_db_exists": False},
        "dbus": {"ok": True},
        "scheduler": {"ok": True, "tasks": 3},
        "ok": True,
    }


def test_cmd_doctor_returns_zero_when_healthy(monkeypatch, capsys):
    import cli

    monkeypatch.setattr(DOC, "run_doctor", _healthy_report)
    rc = cli._cmd_doctor(argparse.Namespace(command="doctor"))
    assert rc == 0
    assert "PkgForge Doctor" in capsys.readouterr().out


def test_cmd_doctor_returns_one_when_unhealthy(monkeypatch):
    import cli

    rep = _healthy_report()
    rep["ok"] = False
    rep["tools"] = {"ok": False, "missing_required": ["pacman"],
                    "missing_optional": [], "debtap": False, "pkexec": False,
                    "distrobox": False}
    monkeypatch.setattr(DOC, "run_doctor", lambda: rep)
    assert cli._cmd_doctor(argparse.Namespace(command="doctor")) == 1
