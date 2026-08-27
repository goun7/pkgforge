"""Tur-64 — fleet.status RPC handler testi."""
from __future__ import annotations

import core.api_server as AS


def test_fleet_status_handler(monkeypatch):
    import core.fleet as FL
    fake = {"backends": {}, "profiles": ["default"], "history_count": 5,
            "policy_level": "STANDARD", "sync_configured": False,
            "age_available": False, "backend_names": ["webdav"]}
    monkeypatch.setattr(FL, "get_fleet_status", lambda: fake)
    yanit = AS.handle_fleet_status({})
    assert yanit == fake


def test_fleet_status_registered():
    assert "fleet.status" in AS.METHODS
