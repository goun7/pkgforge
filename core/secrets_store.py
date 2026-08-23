# mypy: disable-error-code="import-untyped"
"""PkgForge — Secret Service (keyring) client (F4.4).

Minimal org.freedesktop.secrets client over jeepney (blocking IO) storing
small secrets (WebDAV password) in the default collection. Every entry point
degrades gracefully: without jeepney or a running Secret Service the store
reports unavailable and callers fall back to settings.json.
"""

from __future__ import annotations

import os

SERVICE = "org.freedesktop.secrets"
SERVICE_PATH = "/org/freedesktop/secrets"
COLLECTION_DEFAULT = "/org/freedesktop/secrets/aliases/default"


class SecretStoreError(RuntimeError):
    """Raised when the keyring cannot fulfil an operation."""


def bus_has_service() -> bool:
    """True when org.freedesktop.secrets is currently owned on the session bus."""
    try:
        from jeepney import DBusNameFlags
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import open_dbus_connection
    except ImportError:
        return False
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return False
    conn = None
    try:
        conn = open_dbus_connection()
        reply = conn.send_and_get_reply(
            message_bus.NameHasOwner(SERVICE, int(DBusNameFlags.do_not_queue)))
        if reply.header.message_type == reply.header.message_type.ERROR:
            return False
        return bool(reply.body[0])
    except Exception:  # noqa: BLE001 - any bus failure means unavailable
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass


def available() -> bool:
    """jeepney importable AND a Secret Service is on the bus."""
    try:
        import jeepney  # noqa: F401
    except ImportError:
        return False
    return bus_has_service()


class SecretStore:
    """Thin blocking Secret Service wrapper for one attribute set."""

    def __init__(self, attributes: dict[str, str], label: str = "PkgForge"):
        self.attributes = {str(k): str(v) for k, v in attributes.items()}
        self.label = label

    # -- internals ---------------------------------------------------------

    def _conn(self):
        from jeepney.io.blocking import open_dbus_connection

        return open_dbus_connection()

    def _open_session(self, conn) -> str:
        from jeepney import DBusAddress, new_method_call

        svc = DBusAddress(SERVICE_PATH, bus_name=SERVICE,
                          interface="org.freedesktop.secrets.Service")
        call = new_method_call(svc, "OpenSession", "sv",
                               ("plain", ("s", "")))
        reply = conn.send_and_get_reply(call)
        if reply.header.message_type == reply.header.message_type.ERROR:
            raise SecretStoreError(f"OpenSession failed: {reply.body}")
        return str(reply.body[0])

    def _search_items(self, conn) -> tuple[list[str], list[str]]:
        from jeepney import DBusAddress, new_method_call

        svc = DBusAddress(SERVICE_PATH, bus_name=SERVICE,
                          interface="org.freedesktop.secrets.Service")
        call = new_method_call(svc, "SearchItems", "a{ss}", (self.attributes,))
        reply = conn.send_and_get_reply(call)
        if reply.header.message_type == reply.header.message_type.ERROR:
            raise SecretStoreError(f"SearchItems failed: {reply.body}")
        unlocked, locked = reply.body
        return [str(x) for x in unlocked], [str(x) for x in locked]

    def _create_item(self, conn, session: str) -> str:
        from jeepney import DBusAddress, new_method_call

        coll = DBusAddress(COLLECTION_DEFAULT, bus_name=SERVICE,
                           interface="org.freedesktop.secrets.Collection")
        props: dict[str, tuple] = {
            "org.freedesktop.Secret.Item.Label": ("s", self.label),
            "org.freedesktop.Secret.Item.Attributes": ("a{ss}", self.attributes),
        }
        secret = (session, b"", "text/plain", "")
        call = new_method_call(coll, "CreateItem", "a{sv}(oayays)b",
                               (props, secret, True))
        reply = conn.send_and_get_reply(call)
        if reply.header.message_type == reply.header.message_type.ERROR:
            raise SecretStoreError(f"CreateItem failed: {reply.body}")
        item, prompt = str(reply.body[0]), str(reply.body[1])
        if prompt not in ("", "/"):
            raise SecretStoreError(
                "Kilitli koleksiyon: etkileşimli prompt gerekli")
        return item

    def _get_secret(self, conn, session: str, item: str) -> bytes:
        from jeepney import DBusAddress, new_method_call

        addr = DBusAddress(item, bus_name=SERVICE,
                           interface="org.freedesktop.secrets.Item")
        call = new_method_call(addr, "GetSecret", "o", (session,))
        reply = conn.send_and_get_reply(call)
        if reply.header.message_type == reply.header.message_type.ERROR:
            raise SecretStoreError(f"GetSecret failed: {reply.body}")
        _sess, _params, value, _ctype = reply.body[0]
        return bytes(value)

    # -- public API --------------------------------------------------------

    def set_secret(self, value: str) -> None:
        conn = self._conn()
        try:
            session = self._open_session(conn)
            # Replace semantics: delete existing matches first.
            unlocked, locked = self._search_items(conn)
            for item in (*unlocked, *locked):
                from jeepney import DBusAddress, new_method_call

                addr = DBusAddress(item, bus_name=SERVICE,
                                   interface="org.freedesktop.secrets.Item")
                conn.send_and_get_reply(new_method_call(addr, "DeleteItem"))
            self._create_item(conn, session)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def get_secret(self) -> str | None:
        conn = self._conn()
        try:
            session = self._open_session(conn)
            unlocked, _locked = self._search_items(conn)
            items = unlocked or []
            if not items:
                return None
            return self._get_secret(conn, session, items[0]).decode("utf-8")
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def delete_secret(self) -> bool:
        conn = self._conn()
        try:
            from jeepney import DBusAddress, new_method_call

            session = self._open_session(conn)
            del session
            unlocked, locked = self._search_items(conn)
            removed = 0
            for item in (*unlocked, *locked):
                addr = DBusAddress(item, bus_name=SERVICE,
                                   interface="org.freedesktop.secrets.Item")
                conn.send_and_get_reply(new_method_call(addr, "DeleteItem"))
                removed += 1
            return removed > 0
        finally:
            try:
                conn.close()
            except OSError:
                pass


# -- WebDAV-specific helpers ---------------------------------------------------

def webdav_store(username: str) -> SecretStore:
    return SecretStore({"service": "pkgforge", "kind": "webdav",
                        "username": username}, label="PkgForge WebDAV")
