"""Coverage itmesi - core/secrets_store.py D-Bus akisi (sahte baglanti ile)."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

import core.secrets_store as SS
from core.secrets_store import (
    SecretStore,
    SecretStoreError,
    available,
    bus_has_service,
    webdav_store,
)


class FakeConn:
    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []
        self.closed = False

    def send_and_get_reply(self, call):
        self.sent.append(str(call.header if hasattr(call, "header") else call))
        action = self.replies.pop(0)
        if isinstance(action, Exception):
            raise action
        body = action.body if isinstance(action, NS) else action
        return NS(body=body)

    def close(self):
        self.closed = True


def _ok_session_reply():
    return [NS(body=[("s", ""), "/org/sess/1"])]


def test_bus_has_service_guards(monkeypatch):
    real_import = __import__

    def fake_import(name, *a, **k):
        if name.startswith("jeepney"):
            raise ImportError("yok")
        return real_import(name, *a, **k)
    monkeypatch.setitem(__builtins__ if isinstance(__builtins__, dict)
                        else __builtins__.__dict__, "__import__", fake_import)
    assert bus_has_service() is False

    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    assert bus_has_service() is False


def test_available_requires_env_and_probe(monkeypatch):
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    assert available() is False
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/x")

    def boom():
        raise SecretStoreError("activasyon yok")
    monkeypatch.setattr(SS.SecretStore, "_conn", lambda self: boom())
    assert available() is False

    conn = FakeConn(_ok_session_reply())
    monkeypatch.setattr(SS.SecretStore, "_conn", lambda self: conn)
    monkeypatch.setattr(SS.SecretStore, "_open_session",
                        lambda self, c: "/org/sess/1")
    assert available() is True
    assert conn.closed is True


def test_open_session_marshalling(monkeypatch):
    conn = FakeConn([NS(body=[("s", "")])])
    store = SecretStore({"service": "pkgforge"})
    with pytest.raises(SecretStoreError) as ei:
        store._open_session(conn)
    assert "beklenmeyen" in str(ei.value)

    conn2 = FakeConn([NS(body=[("s", ""), "gecersiz"])])
    with pytest.raises(SecretStoreError) as ei2:
        store._open_session(conn2)
    assert "gecersiz" in str(ei2.value)

    ok = FakeConn([NS(body=[("s", ""), "/org/sess/9"])])
    assert store._open_session(ok) == "/org/sess/9"


def test_search_items_shapes(monkeypatch):
    store = SecretStore({"service": "pkgforge"})
    two = FakeConn([NS(body=[["/it1"], ["/it2"]])])
    u, l = store._search_items(two)
    assert (u, l) == (["/it1"], ["/it2"])

    one = FakeConn([NS(body=[["/it3"]])])
    u2, l2 = store._search_items(one)
    assert (u2, l2) == (["/it3"], [])

    err = FakeConn([SecretStoreError("bus koptu")])
    with pytest.raises(SecretStoreError):
        store._search_items(err)


def test_create_item_prompt_rejected(monkeypatch):
    store = SecretStore({"service": "pkgforge"}, label="L")
    prompt = FakeConn([NS(body=["/org/item/1", "/org/prompt/1"])])
    with pytest.raises(SecretStoreError) as ei:
        store._create_item(prompt, "/sess")
    assert "prompt" in str(ei.value)

    ok = FakeConn([NS(body=["/org/item/1", "/"])])
    assert store._create_item(ok, "/sess") == "/org/item/1"


def test_get_set_delete_roundtrip(monkeypatch):
    store = webdav_store("ali")
    assert store.label == "PkgForge WebDAV"
    assert store.attributes["username"] == "ali"

    # set: session + empty search + delete skipped + create
    set_conn = FakeConn([
        *_ok_session_reply(),
        NS(body=[[], []]),
        NS(body=["/org/item/new", "/"]),
    ])
    monkeypatch.setattr(SS.SecretStore, "_conn", lambda self: set_conn)
    store.set_secret("gizli")
    assert set_conn.closed is True

    # get: session + search hit + secret value
    get_conn = FakeConn([
        *_ok_session_reply(),
        NS(body=[["/org/item/new"], []]),
        NS(body=[("/s", b"", b"gizli-deger", "text/plain")]),
    ])
    monkeypatch.setattr(SS.SecretStore, "_conn", lambda self: get_conn)
    assert store.get_secret() == "gizli-deger"

    # get miss returns None without GetSecret call
    miss_conn = FakeConn([
        *_ok_session_reply(),
        NS(body=[[], []]),
    ])
    monkeypatch.setattr(SS.SecretStore, "_conn", lambda self: miss_conn)
    assert store.get_secret() is None

    # delete removes both unlocked+locked and reports truthfully
    del_conn = FakeConn([
        *_ok_session_reply(),
        NS(body=[["/a"], ["/b"]]),
        NS(body=["/"]),
        NS(body="/"),
    ])
    monkeypatch.setattr(SS.SecretStore, "_conn", lambda self: del_conn)
    assert store.delete_secret() is True

    none_conn = FakeConn([
        *_ok_session_reply(),
        NS(body=[[], []]),
    ])
    monkeypatch.setattr(SS.SecretStore, "_conn", lambda self: none_conn)
    assert store.delete_secret() is False