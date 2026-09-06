"""Faz 4 (F4.4) — keyring integration: graceful degradation + migration."""
from __future__ import annotations

import base64
from typing import ClassVar

import pytest

import core.api_server as A
from core.cloud_sync import SyncError, _webdav_target


@pytest.fixture()
def cfg_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    import config
    import i18n

    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(i18n, "_settings_cache", {}, raising=False)
    return tmp_path


class _FakeStore:
    instances: ClassVar[list[_FakeStore]] = []

    def __init__(self, username: str):
        self.username = username
        self.saved: str | None = None
        _FakeStore.instances.append(self)

    def get_secret(self) -> str | None:
        return self.saved

    def set_secret(self, value: str) -> None:
        self.saved = value


def _keyring_on(monkeypatch: pytest.MonkeyPatch, saved: str | None = "pw"):
    import core.secrets_store as SS

    monkeypatch.setattr(SS, "available", lambda: True)
    holder = {"saved": saved}

    def make(user: str):
        fs = _FakeStore(user)
        fs.saved = holder["saved"]
        return fs

    monkeypatch.setattr(SS, "webdav_store", make)
    return holder


# --- cloud_sync reads keyring first -------------------------------------------

def test_webdav_uses_keyring_password_over_settings(
        cfg_root, monkeypatch: pytest.MonkeyPatch):
    from i18n import load_settings, save_settings

    save_settings({**load_settings(), "sync_url": "https://dav.example",
                   "sync_username": "ali", "sync_password": "legacy"})
    _keyring_on(monkeypatch, saved="kring")
    _url, headers = _webdav_target()
    token = base64.b64encode(b"ali:kring").decode()
    assert headers["Authorization"] == f"Basic {token}"


def test_webdav_never_reads_plaintext_when_no_secret(
        cfg_root, monkeypatch: pytest.MonkeyPatch):
    """Keyring up but no secret stored -> empty password, NOT 'legacy'."""
    from i18n import load_settings, save_settings

    save_settings({**load_settings(), "sync_url": "https://dav.example",
                   "sync_username": "ali", "sync_password": "legacy"})
    _keyring_on(monkeypatch, saved=None)
    _url, headers = _webdav_target()
    token = base64.b64encode(b"ali:").decode()
    assert headers["Authorization"] == f"Basic {token}"
    assert "legacy" not in headers["Authorization"]


def test_webdav_aborts_without_keyring_service(
        cfg_root, monkeypatch: pytest.MonkeyPatch):
    """No Secret Service -> hard stop, plaintext value stays unused."""
    import core.secrets_store as SS
    from i18n import load_settings, save_settings

    save_settings({**load_settings(), "sync_url": "https://dav.example",
                   "sync_username": "ali", "sync_password": "legacy"})
    monkeypatch.setattr(SS, "available", lambda: False)
    with pytest.raises(SS.SecretStoreError):
        _webdav_target()


# --- sync.config stores into keyring & migrates off plaintext -----------------

def test_config_prefers_keyring_and_drops_plaintext(
        cfg_root, monkeypatch: pytest.MonkeyPatch):
    from i18n import load_settings, save_settings

    save_settings(load_settings())
    _keyring_on(monkeypatch)
    out = A.handle_sync_config({"sync_url": "https://x", "sync_username": "ayse",
                                "sync_password": "s3cret"})
    assert out == {"ok": True, "password_stored": "keyring"}
    assert "sync_password" not in load_settings()
    assert _FakeStore.instances[-1].saved == "s3cret"
    assert _FakeStore.instances[-1].username == "ayse"


def test_config_never_stores_plaintext_without_keyring(
        cfg_root, monkeypatch: pytest.MonkeyPatch):
    from i18n import load_settings, save_settings

    save_settings(load_settings())
    import core.secrets_store as SS

    monkeypatch.setattr(SS, "available", lambda: False)
    out = A.handle_sync_config({"sync_username": "ayse",
                                "sync_password": "plain"})
    assert out["ok"] is True
    assert out["password_stored"] == "rejected"
    assert out["warning"]
    assert "sync_password" not in load_settings()


def test_push_pull_still_work_end_to_end_with_keyring(
        cfg_root, tmp_path_factory, monkeypatch: pytest.MonkeyPatch):
    """Keyring path must not break the WebDAV roundtrip plumbing."""
    from core.cloud_sync import webdav_push
    from i18n import load_settings, save_settings

    _seed()
    save_settings({**load_settings(), "sync_url": "", })
    with pytest.raises(SyncError):
        webdav_push()  # unconfigured server still rejected first


def _seed():

    from config import profile_config_dir
    d = profile_config_dir("default")
    d.mkdir(parents=True, exist_ok=True)
    (d / "settings.json").write_text('{"theme": "dark"}', encoding="utf-8")


# --- live Secret Service roundtrip (skipped without org.freedesktop.secrets) --

@pytest.mark.skipif(
    not __import__("core.secrets_store", fromlist=["available"]).available(),
    reason="no Secret Service on session bus")
def test_live_secret_service_roundtrip():
    from core.secrets_store import webdav_store

    store = webdav_store("roundtrip-user")
    store.set_secret("topsecret")
    try:
        assert store.get_secret() == "topsecret"
    finally:
        store.delete_secret()
    assert store.get_secret() is None
