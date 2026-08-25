"""Coverage itmesi — core/http_api meta router."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

import core.http_api.meta as M


def test_app_and_tools(monkeypatch):
    v = M.handle_app_version({})
    assert "name" in v and "version" in v

    monkeypatch.setattr(M, "discover_tools", lambda: NS(
        pacman="/p", makepkg="", distrobox=None,
        missing_required=("pacman",), missing_optional=()))
    st = M.handle_tools_status({})
    assert st == {"has_pacman": True, "has_makepkg": False,
                  "has_distrobox": False, "missing_required": ["pacman"],
                  "missing_optional": []}


def test_settings_roundtrip(monkeypatch):
    store = {"tema": "koyu"}
    monkeypatch.setattr(M, "load_settings", lambda: dict(store))
    monkeypatch.setattr(M, "save_settings", lambda s: store.update(s))
    assert M.handle_settings_get({}) == {"tema": "koyu"}
    out = M.handle_settings_set({"dil": "tr"})
    assert out == {"ok": True} and store["dil"] == "tr"


def test_doctor_wrapped_policy_get(monkeypatch):
    monkeypatch.setattr("core.doctor.run_doctor", lambda: {"ok": 1})
    monkeypatch.setattr("core.stats_wrapped.build_wrapped",
                        lambda year=None: {"yil": year})
    import core.policy_engine as PE
    monkeypatch.setattr(PE, "policy_from_settings",
                        lambda: NS(value="strict"))
    assert M.handle_app_doctor({}) == {"ok": 1}
    assert M.handle_stats_wrapped({"year": "2025"}) == {"yil": 2025}
    assert M.handle_stats_wrapped({}) == {"yil": None}
    assert M.handle_policy_get({}) == {"level": "strict"}


def test_policy_evaluate_and_set(monkeypatch):
    import core.policy_engine as PE
    got = []
    monkeypatch.setattr(PE, "evaluate", lambda r: got.append(r) or {"decision": "pass"})
    assert M.handle_policy_evaluate({"report": {"x": 1}}) == {"decision": "pass"}
    assert got == [{"x": 1}]

    store = {}
    monkeypatch.setattr(M, "load_settings", lambda: dict(store))
    monkeypatch.setattr(M, "save_settings", lambda s: store.update(s))
    out = M.handle_policy_set({"level": "STRICT"})
    assert out == {"ok": True, "level": "strict"}
    with pytest.raises(ValueError):
        M.handle_policy_set({"level": "kotu"})


def test_system_health(monkeypatch):
    class FakeDB:
        def get_usage_stats(self):
            return {"total": 4, "by_status": {"installed": 2, "converted": 1, "install_failed": 1},
                    "by_type": {"deb": 3}, "by_arch": {"x86_64": 4}, "url_count": 1,
                    "first_seen": "a", "last_seen": "b"}
    monkeypatch.setattr("core.history_db.HistoryDB", FakeDB)
    h = M.handle_system_health({})
    assert h["total"] == 4 and h["success_rate"] == 75.0
    assert h["failed"] == 1 and h["by_arch"] == {"x86_64": 4}