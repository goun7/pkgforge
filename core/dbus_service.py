"""PkgForge — D-Bus service for third-party integration (C1).

Exposes the sidecar's JSON-RPC method registry on the session bus as
org.pkgforge.App: third-party tools call Call(method: String, params_json: String)
and receive the JSON-RPC response as a JSON string. Requires the optional,
pure-Python 'jeepney' package; without it every entry point degrades to a
clear "unavailable" status instead of crashing.
"""

# mypy: disable-error-code="import-untyped"
from __future__ import annotations

import json
import os
import threading
from typing import Any

DEFAULT_BUS_NAME = "org.pkgforge.App"
OBJECT_PATH = "/org/pkgforge/App"
INTERFACE = "org.pkgforge.App"

_lock = threading.Lock()
_service: PkgForgeService | None = None


def is_available() -> bool:
    """True when the optional jeepney dependency is importable."""
    try:
        import jeepney  # noqa: F401
    except ImportError:
        return False
    return True


def service_status() -> dict[str, Any]:
    """Report availability/running state for UI and dbus.status."""
    with _lock:
        running = bool(_service and _service.is_running())
    return {
        "available": is_available(),
        "running": running,
        "bus_name": DEFAULT_BUS_NAME,
    }


class ServiceError(RuntimeError):
    """Raised for D-Bus service failures with a user-facing message."""


def _mutations_allowed() -> bool:
    """F4.2 policy: session-bus callers are read-only unless opted in."""
    import i18n

    return bool(i18n.load_settings().get("dbus_allow_mutations", False))


def _handle_call(method_name: str, params_json: str,
                 caller_uid: int | None = None) -> str:
    """Map one D-Bus Call onto the sidecar JSON-RPC dispatcher.

    F5.1: caller_uid comes from the bus driver (GetConnectionUnixUser).
    Fail-closed: unknown caller (None) can never reach mutations even when
    the policy flag is on - only same-UID local callers pass.
    """
    from core.api_server import _READ_METHODS, METHODS, _dispatch

    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as exc:
        response = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"}}
    else:
        if not isinstance(params, dict):
            params = {}
        known = method_name in METHODS
        if known and method_name not in _READ_METHODS:
            if not _mutations_allowed():
                response = {"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32000,
                                      "message": (
                                          "D-Bus policy: salt-okunur. "
                                          "Ayarlar > D-Bus Servisi uzerinden "
                                          "yazma izni verin (dbus.set_policy).")}}
            elif caller_uid != _own_uid():
                # F5.1: session-bus peers are NOT trusted by default.
                response = {"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32002,
                                      "message": (
                                          f"D-Bus arayani farkli kullanici "
                                          f"(uid={caller_uid}); yazma reddedildi.")}}
            else:
                response = _dispatch({"jsonrpc": "2.0", "id": 1,
                                      "method": method_name, "params": params})
        else:
            response = _dispatch({"jsonrpc": "2.0", "id": 1,
                                  "method": method_name, "params": params})
    return json.dumps(response, ensure_ascii=False)


def _own_uid() -> int:
    """Own Unix UID; module-level so tests can pin it."""
    return os.getuid()


def _caller_uid(conn, sender):
    """Resolve the Unix UID behind a bus name; None when undeterminable."""
    if not sender:
        return None
    try:
        from jeepney import DBusAddress, new_method_call

        driver = DBusAddress("/org/freedesktop/DBus",
                             bus_name="org.freedesktop.DBus",
                             interface="org.freedesktop.DBus")
        reply = conn.send_and_get_reply(
            new_method_call(driver, "GetConnectionUnixUser", "s", (sender,)))
        return int(reply.body[0])
    except Exception:  # noqa: BLE001 - any failure means unverified caller
        return None


class PkgForgeService:
    """Serve org.pkgforge.App.Call() on the session bus (blocking io)."""

    def __init__(self, bus_name: str = DEFAULT_BUS_NAME):
        self.bus_name = bus_name
        self._conn: Any = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if not is_available():
            raise ServiceError(
                "D-Bus servisi için opsiyonel 'jeepney' paketi gerekli: "
                "pip install jeepney"
            )
        if self.is_running():
            raise ServiceError("D-Bus servisi zaten çalışıyor")

        from jeepney import DBusNameFlags, MessageType
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import open_dbus_connection

        try:
            conn = open_dbus_connection()
        except Exception as exc:
            raise ServiceError(f"Oturum veriyoluna bağlanılamadı: {exc}") from exc

        reply = conn.send_and_get_reply(
            message_bus.RequestName(self.bus_name, int(DBusNameFlags.do_not_queue)))
        if reply.header.message_type != MessageType.method_return:
            detail = ""
            if reply.body:
                detail = str(reply.body[0])
            conn.close()
            raise ServiceError(
                f"Veriyolu adı alınamadı ({self.bus_name}): {detail}"
            )

        self._conn = conn
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve_loop,
                                        name="pkgforge-dbus", daemon=True)
        self._thread.start()

    def _serve_loop(self) -> None:
        from jeepney import HeaderFields, MatchRule, MessageType, new_method_return
        from jeepney.io.blocking import FilterHandle  # noqa: F401 (type ref)

        rule = MatchRule(type="method_call", interface=INTERFACE)
        handle = self._conn.filter(rule)
        queue = handle.queue
        try:
            while not self._stop.is_set():
                try:
                    self._conn.recv_messages(timeout=0.2)
                except TimeoutError:
                    pass
                while True:
                    try:
                        msg = queue.popleft()
                    except IndexError:
                        break
                    member = msg.header.fields.get(HeaderFields.member)
                    if (msg.header.message_type == MessageType.method_call
                            and member == "Call"):
                        sender = msg.header.fields.get(HeaderFields.sender)
                        try:
                            uid = _caller_uid(self._conn, sender)
                        except Exception:  # noqa: BLE001 - fail closed
                            uid = None
                        try:
                            payload = _handle_call(msg.body[0], msg.body[1],
                                                   caller_uid=uid)
                        except Exception as exc:  # noqa: BLE001
                            payload = json.dumps(
                                {"jsonrpc": "2.0", "id": None,
                                 "error": {"code": -32000, "message": str(exc)}})
                        self._conn.send_message(
                            new_method_return(msg, "s", (payload,)))
        except OSError:
            pass  # connection closed underneath us during stop
        finally:
            handle.close()

    def stop(self) -> None:
        self._stop.set()
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._thread = None
        self._conn = None


def start_default() -> dict[str, Any]:
    """Start (once) the default shared service instance."""
    global _service
    with _lock:
        if _service is not None and _service.is_running():
            raise ServiceError("D-Bus servisi zaten çalışıyor")
        svc = PkgForgeService()
        svc.start()
        _service = svc
    return {"started": True, "bus_name": DEFAULT_BUS_NAME}


def stop_default() -> dict[str, Any]:
    global _service
    with _lock:
        if _service is not None:
            _service.stop()
            _service = None
    return {"stopped": True}
