"""Coverage itmesi — core/secrets_store.py dbus hata dallari ve yardimcilar."""
from __future__ import annotations

import sys
from types import SimpleNamespace as NS

import pytest

import core.secrets_store as SS


@pytest.fixture(autouse=True)
def _no_dbus_env(monkeypatch):
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)


def test_bus_has_service_without_jeepney(monkeypatch):
    monkeypatch.setitem(sys.modules, "jeepney", None)
    assert SS.bus_has_service() is False


def test_available_without_jeepney_or_bus(monkeypatch):
    monkeypatch.setitem(sys.modules, "jeepney", None)
    assert SS.available() is False


class _BoomConn:
    def send_and_get_reply(self, call):
        raise OSError("otobus koptu")

    def close(self):
        pass


def test_store_open_session_send_failure_raises(monkeypatch):
    s = SS.SecretStore({"service": "pkgforge", "kind": "probe"})
    monkeypatch.setattr(s, "_conn", lambda: _BoomConn())
    with pytest.raises(SS.SecretStoreError, match="OpenSession failed"):
        s._open_session(_BoomConn())


def test_store_open_session_short_body_raises():
    s = SS.SecretStore({"service": "x", "kind": "probe"})
    conn = NS(send_and_get_reply=lambda c: NS(body=("/tmp/out",)))
    with pytest.raises(SS.SecretStoreError):
        s._open_session(conn)


class _FakeConn:
    """Arama/olusturma/okuma akisini betimleyen sahte veriyolu."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def send_and_get_reply(self, call):
        self.calls.append(call)
        return self.replies.pop(0)

    def close(self):
        pass


def _session_reply():
    return NS(body=("cikti", "/session/1"))


def test_set_secret_replaces_and_prompt_blocks(monkeypatch):
    s = SS.SecretStore({"service": "pkgforge", "kind": "webdav"}, label="L")
    # arama -> ([eski], [kilitli]); olusturma -> prompt'lu yanit
    conn = _FakeConn([
        _session_reply(),
        NS(body=("/d1",)),   # DeleteItem eski
        NS(body=("/d2",)),   # DeleteItem kilitli
        NS(body=("/yeni", "/prompt/1")),  # prompt gerekli
    ])
    monkeypatch.setattr(s, "_conn", lambda: conn)
    monkeypatch.setattr(s, "_search_items",
                        lambda c: (["/item/eski"], ["/item/kilitli"]))
    # gercek _create_item calisir; prompt'lu yanit hata dogurur
    with pytest.raises(SS.SecretStoreError,
                       match="Kilitli koleksiyon"):
        s.set_secret("parola")


def test_get_secret_empty_returns_none(monkeypatch):
    s = SS.SecretStore({"service": "pkgforge", "kind": "webdav"})
    monkeypatch.setattr(s, "_conn", lambda: _FakeConn([_session_reply()]))
    monkeypatch.setattr(s, "_search_items", lambda c: ([], []))
    assert s.get_secret() is None


def test_get_secret_decodes_value(monkeypatch):
    s = SS.SecretStore({"service": "pkgforge", "kind": "webdav"})
    conn = _FakeConn([
        _session_reply(),
        NS(body=(("/s", b"", b"gizli", "text/plain"),)),
    ])
    monkeypatch.setattr(s, "_conn", lambda: conn)
    monkeypatch.setattr(s, "_search_items", lambda c: (["/item/1"], []))
    monkeypatch.setattr(s, "_get_secret", lambda c, sess, item: b"gizli")
    assert s.get_secret() == "gizli"


def test_delete_secret_counts_and_close_oserror_swallowed(monkeypatch):
    class _CloseBoom(_FakeConn):
        def close(self):
            raise OSError("kapanmadi")
    s = SS.SecretStore({"service": "p", "kind": "w"})
    conn = _CloseBoom([
        _session_reply(),
        NS(body=([["/i1"]], [["/i2"]])),
        NS(body=()),
        NS(body=()),
    ])
    monkeypatch.setattr(s, "_conn", lambda: conn)

    def fake_search(c):
        return (["/i1"], ["/i2"])
    monkeypatch.setattr(s, "_search_items", fake_search)
    assert s.delete_secret() is True  # close hatasi yutulur


def test_delete_secret_no_items_false(monkeypatch):
    s = SS.SecretStore({"service": "p", "kind": "w"})
    monkeypatch.setattr(s, "_conn", lambda: _FakeConn([_session_reply()]))
    monkeypatch.setattr(s, "_search_items", lambda c: ([], []))
    assert s.delete_secret() is False


def test_webdav_helpers_build_stores():
    st = SS.webdav_store("kullanici")
    assert st.attributes["kind"] == "webdav"
