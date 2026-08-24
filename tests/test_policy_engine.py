"""Faz 5 (F5.19) — politika motoru: profil bazli compat esikleri."""
from __future__ import annotations

import pytest

from core.compatibility_checker import (
    CheckResult,
    CheckSeverity,
    CompatibilityReport,
)
from core.policy_engine import PolicyLevel, evaluate, policy_from_settings


def _report(*severities):
    checks = [
        CheckResult(name=f"c{i}", severity=s, message="m")
        for i, s in enumerate(severities)
    ]
    return CompatibilityReport(checks=checks)


# --- policy_from_settings ------------------------------------------------

def test_default_policy_is_standard():
    assert policy_from_settings({}) is PolicyLevel.STANDARD


def test_policy_reads_strict():
    assert policy_from_settings({"compat_policy": "strict"}) is PolicyLevel.STRICT


def test_policy_invalid_falls_back_to_standard():
    assert policy_from_settings({"compat_policy": "nope"}) is PolicyLevel.STANDARD


# --- evaluate (rapor nesnesi) -------------------------------------------

def test_pass_allowed_under_both():
    r = _report(CheckSeverity.PASS)
    assert evaluate(r, PolicyLevel.STANDARD)["allowed"] is True
    assert evaluate(r, PolicyLevel.STRICT)["allowed"] is True


def test_warning_allowed_standard_blocked_strict():
    r = _report(CheckSeverity.WARNING)
    assert evaluate(r, PolicyLevel.STANDARD)["allowed"] is True
    assert evaluate(r, PolicyLevel.STRICT)["allowed"] is False


def test_error_blocked_under_both():
    r = _report(CheckSeverity.PASS, CheckSeverity.ERROR)
    assert evaluate(r, PolicyLevel.STANDARD)["allowed"] is False
    assert evaluate(r, PolicyLevel.STRICT)["allowed"] is False


# --- evaluate (dict formu) ----------------------------------------------

def test_evaluate_dict_form():
    rep = {"checks": [{"severity": "warning"}, {"severity": "pass"}]}
    assert evaluate(rep, PolicyLevel.STANDARD)["allowed"] is True
    assert evaluate(rep, PolicyLevel.STRICT)["allowed"] is False


def test_evaluate_none_report_not_allowed():
    out = evaluate(None, PolicyLevel.STANDARD)
    assert out["allowed"] is False
    assert out["overall"] == "unknown"


def test_evaluate_malformed_dict_not_allowed():
    out = evaluate({"checks": "not-a-list"}, PolicyLevel.STANDARD)
    assert out["allowed"] is False


# --- RPC handler'lari ----------------------------------------------------

def test_rpc_policy_evaluate():
    import core.api_server as A

    rep = {"checks": [{"severity": "error"}]}
    out = A.handle_policy_evaluate({"report": rep})
    assert out["allowed"] is False


def test_rpc_policy_get_set_roundtrip(monkeypatch, tmp_path):
    import core.api_server as A

    store = {}
    monkeypatch.setattr(A, "load_settings", lambda: dict(store))

    def _save(s):
        store.clear()
        store.update(s)

    monkeypatch.setattr(A, "save_settings", _save)

    assert A.handle_policy_get({})["level"] == "standard"
    assert A.handle_policy_set({"level": "strict"})["level"] == "strict"
    assert store["compat_policy"] == "strict"


def test_rpc_policy_set_rejects_invalid():
    import core.api_server as A

    with pytest.raises(ValueError):
        A.handle_policy_set({"level": "hack"})
