"""Coverage itmesi — core/http_api read router (F5.11 okuma handlerlari)."""
from __future__ import annotations

from types import SimpleNamespace as NS

import core.http_api.read as R


def test_history_list(monkeypatch):
    seen = []
    class FakeDB:
        def get_history(self, limit=100):
            seen.append(limit)
            return [NS(id=1, timestamp="t", package_name="demo",
                       package_type="deb", status="converted",
                       original_file="d.deb", source_url=None)]
    monkeypatch.setattr("core.history_db.HistoryDB", FakeDB)
    rows = R.handle_history_list({"limit": 5})
    assert rows[0]["package_name"] == "demo" and rows[0]["source_url"] == ""
    R.handle_history_list({})
    assert seen == [5, 100]


def test_plugin_and_profile_and_dbus(monkeypatch):
    monkeypatch.setattr("core.plugins.marketplace.list_installed_plugins", lambda: [1])
    monkeypatch.setattr("core.plugins.marketplace.fetch_available_plugins",
                        lambda offline=False: {"offline": offline})
    monkeypatch.setattr("core.plugins.marketplace.audit_plugins", lambda: {"ok": True})
    monkeypatch.setattr("core.profiles.list_profiles", lambda: ["varsayilan"])
    monkeypatch.setattr("core.profiles.current_profile", lambda: "varsayilan")
    monkeypatch.setattr("core.dbus_service.service_status", lambda: {"up": False})

    assert R.handle_plugin_list({}) == [1]
    assert R.handle_plugin_available({}) == {"offline": False}
    assert R.handle_plugin_available({"offline": True}) == {"offline": True}
    assert R.handle_plugin_audit({}) == {"ok": True}
    assert R.handle_profile_list({}) == ["varsayilan"]
    assert R.handle_profile_current({}) == {"name": "varsayilan"}
    assert R.handle_dbus_status({}) == {"up": False}