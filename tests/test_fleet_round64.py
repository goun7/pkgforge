"""Tur-64 — core.fleet.get_fleet_status birim testleri."""
from __future__ import annotations

import core.fleet as FL


def test_full_status(monkeypatch):
    monkeypatch.setattr(FL.shutil, "which",
                        lambda n: "/usr/bin/" + n if n in ("git", "rclone") else None)
    import i18n
    monkeypatch.setattr(i18n, "load_settings",
                        lambda: {"sync_url": "https://dav/x", "policy_level": "strict"})
    import core.cloud_sync as CS
    monkeypatch.setattr(CS, "_profile_names", lambda: ["default", "is"])
    import core.history_db as HD

    class FakeDB:
        def get_history(self, limit=100000):
            return [1, 2, 3]

    monkeypatch.setattr(HD, "HistoryDB", FakeDB)
    import core.policy_engine as PE

    class FakeLevel:
        name = "STRICT"

    monkeypatch.setattr(PE, "policy_from_settings", lambda s: FakeLevel())
    import core.sync_backends as SB
    monkeypatch.setattr(SB, "age_available", lambda: True)

    res = FL.get_fleet_status()
    assert res["sync_configured"] is True
    assert res["backends"]["webdav"]["configured"] is True
    assert res["backends"]["git"]["available"] is True
    assert res["backends"]["rclone-s3"]["available"] is True
    assert res["profiles"] == ["default", "is"]
    assert res["history_count"] == 3
    assert res["policy_level"] == "STRICT"
    assert res["age_available"] is True
    assert res["backend_names"] == ["webdav", "git", "rclone-s3"]


def test_no_binaries_no_sync(monkeypatch):
    monkeypatch.setattr(FL.shutil, "which", lambda n: None)
    import i18n
    monkeypatch.setattr(i18n, "load_settings", lambda: {})
    import core.sync_backends as SB
    monkeypatch.setattr(SB, "age_available", lambda: False)

    res = FL.get_fleet_status()
    assert res["sync_configured"] is False
    assert res["backends"]["git"]["available"] is False
    assert res["backends"]["rclone-s3"]["available"] is False
    assert res["age_available"] is False


def test_settings_load_fails(monkeypatch):
    monkeypatch.setattr(FL.shutil, "which", lambda n: None)
    import i18n

    def boom():
        raise RuntimeError("settings bozuk")

    monkeypatch.setattr(i18n, "load_settings", boom)
    res = FL.get_fleet_status()
    assert res["sync_configured"] is False


def test_profiles_fail(monkeypatch):
    monkeypatch.setattr(FL.shutil, "which", lambda n: None)
    import core.cloud_sync as CS

    def boom():
        raise RuntimeError("profil bozuk")

    monkeypatch.setattr(CS, "_profile_names", boom)
    res = FL.get_fleet_status()
    assert res["profiles"] == []


def test_history_fail(monkeypatch):
    monkeypatch.setattr(FL.shutil, "which", lambda n: None)
    import core.history_db as HD

    class FakeDB:
        def get_history(self, limit=100000):
            raise RuntimeError("db bozuk")

    monkeypatch.setattr(HD, "HistoryDB", FakeDB)
    res = FL.get_fleet_status()
    assert res["history_count"] == 0


def test_policy_fail(monkeypatch):
    monkeypatch.setattr(FL.shutil, "which", lambda n: None)
    import core.policy_engine as PE

    def boom(s):
        raise RuntimeError("policy bozuk")

    monkeypatch.setattr(PE, "policy_from_settings", boom)
    res = FL.get_fleet_status()
    assert res["policy_level"] == "STANDARD"
