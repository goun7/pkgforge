"""Faz 5 (F5.1) — single-source capabilities + D-Bus caller UID gate."""
from __future__ import annotations

import json

import pytest

import core.capabilities as CAPS
import core.dbus_service as D
import core.privileged as P


def test_reader_set_is_the_expected_readonly_methods():
    assert CAPS.http_reader_methods() == frozenset({
        "app.version", "app.doctor", "tools.status", "settings.get",
        "history.list", "schedule.get", "profile.list", "profile.current",
        "queue.list", "plugin.list", "plugin.available", "plugin.audit",
        "dbus.status",
    })


def test_api_server_consumes_capabilities_not_a_copy():
    import core.api_server as A

    assert A._READ_METHODS is not None
    assert set(A._READ_METHODS) == set(CAPS.http_reader_methods())


def test_privileged_actions_come_from_capabilities():
    ids = {a[0] for a in P.ACTIONS}
    caps_ids = {a[0] for a in CAPS.polkit_actions()}
    assert ids == caps_ids == {
        "org.pkgforge.install",
        "org.pkgforge.delta-update",
        "org.pkgforge.snapshot-cleanup",
    }


def test_artifact_json_matches_module():
    assert CAPS.artifact_matches(), (
        "capabilities.json bayatladı: python -m core.capabilities --emit")


# --- D-Bus caller-UID gate ----------------------------------------------------

@pytest.fixture()
def mutations_on(tmp_path, monkeypatch):
    import config
    import i18n

    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(i18n, "_settings_cache", {}, raising=False)
    monkeypatch.setattr(D, "_own_uid", lambda: 1000)
    monkeypatch.setattr(
        i18n, "load_settings",
        lambda: {"dbus_allow_mutations": True})


def _err(payload):
    return payload.get("error", {})


def test_same_uid_caller_passes_gate(mutations_on):
    out = json.loads(D._handle_call("settings.get", "{}", caller_uid=1000))
    assert "result" in out  # read methods unaffected by uid layer

    # mutation with SAME uid -> reaches dispatcher (settings.set persists)
    out = json.loads(D._handle_call(
        "settings.set", '{"dry_run": true}', caller_uid=1000))
    assert "error" not in out or _err(out).get("code") != -32002


def test_foreign_uid_is_rejected_even_when_allowed(mutations_on):
    out = json.loads(D._handle_call(
        "settings.set", '{"dry_run": true}', caller_uid=2000))
    assert _err(out)["code"] == -32002
    assert "farkli kullanici" in _err(out)["message"]


def test_unknown_caller_fails_closed(mutations_on):
    out = json.loads(D._handle_call(
        "settings.set", '{"dry_run": true}', caller_uid=None))
    assert _err(out)["code"] == -32002


def test_reads_still_work_for_unknown_caller(mutations_on):
    out = json.loads(D._handle_call("app.version", "{}", caller_uid=None))
    assert "result" in out