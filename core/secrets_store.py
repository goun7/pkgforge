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
    """True when the Secret Service name is owned or activatable right now.

    Kept for diagnostics; available() is the authoritative probe because it
    exercises a real OpenSession (activation-safe).
    """
    try:
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
            message_bus.NameHasOwner(SERVICE))
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
    """jeepney importable AND a Secret Service answers OpenSession.

    F5.6: NameHasOwner alone is not enough — services like kwalletd's
    secretservicecompat are D-Bus-activatable and only appear after the
    first call. We therefore probe with a real (throwaway) OpenSession and
    fail closed on any error.
    """
    try:
        import jeepney  # noqa: F401
    except ImportError:
        return False
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return False
    probe = SecretStore({"service": "pkgforge", "kind": "probe"})
    conn = None
    try:
        conn = probe._conn()
        session = probe._open_session(conn)
        return bool(session)
    except Exception:  # noqa: BLE001 - activation failure == unavailable
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass


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
        try:
            reply = conn.send_and_get_reply(call)
        except Exception as exc:
            raise SecretStoreError(f"OpenSession failed: {exc}") from exc
        return str(reply.body[0])

    def _search_items(self, conn) -> tuple[list[str], list[str]]:
        from jeepney import DBusAddress, new_method_call

        svc = DBusAddress(SERVICE_PATH, bus_name=SERVICE,
                          interface="org.freedesktop.secrets.Service")
        call = new_method_call(svc, "SearchItems", "a{ss}", (self.attributes,))
        try:
            reply = conn.send_and_get_reply(call)
        except Exception as exc:
            raise SecretStoreError(f"SearchItems failed: {exc}") from exc
        # Spec says (unlocked, locked); kwalletd returns a single list.
        if len(reply.body) == 2:
            unlocked, locked = reply.body
        else:
            unlocked = reply.body[0] if reply.body else []
            locked = []
        return [str(x) for x in unlocked], [str(x) for x in locked]

    def _create_item(self, conn, session: str) -> str:
        from jeepney import DBusAddress, new_method_call

        coll = DBusAddress(COLLECTION_DEFAULT, bus_name=SERVICE,
                           interface="org.freedesktop.secrets.Collection")
        props: dict[str, tuple] = {
            "org.freedesktop.Secret.Item.Label": ("s", self.label),
            "org.freedesktop.Secret.Item.Attributes": ("a{ss}", self.attributes),
        }
        # Secret struct per spec: (session:o, parameters:ay, value:ay,
        # content_type:s) — the params/value split is easy to get wrong.
        secret = (session, b"", b"", "text/plain")
        call = new_method_call(coll, "CreateItem", "a{sv}(oayays)b",
                               (props, secret, True))
        try:
            reply = conn.send_and_get_reply(call)
        except Exception as exc:
            raise SecretStoreError(f"CreateItem failed: {exc}") from exc
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
        try:
            reply = conn.send_and_get_reply(call)
        except Exception as exc:
            raise SecretStoreError(f"GetSecret failed: {exc}") from exc
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
