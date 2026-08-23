"""Faz 3 (C1) tests — D-Bus service bridge."""
from __future__ import annotations

import json
import os
import uuid

import pytest

from core import dbus_service
from core.dbus_service import PkgForgeService, ServiceError


# --- pure / offline units ---------------------------------------------------

def test_is_available_returns_bool():
    assert isinstance(dbus_service.is_available(), bool)


def test_status_shape():
    status = dbus_service.service_status()
    assert set(status) == {"available", "running", "bus_name"}
    assert status["bus_name"] == dbus_service.DEFAULT_BUS_NAME


def test_handle_call_app_version():
    payload = json.loads(dbus_service._handle_call("app.version", "{}"))
    assert payload["result"]["name"] == "PkgForge"


def test_handle_call_bad_params_json_is_parse_error():
    payload = json.loads(dbus_service._handle_call("app.version", "{broken"))
    assert payload["error"]["code"] == -32700


def test_handle_call_unknown_method():
    payload = json.loads(
        dbus_service._handle_call("nope.nope", "{}"))
    assert payload["error"]["code"] == -32601


def test_start_requires_jeepney(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dbus_service, "is_available", lambda: False)
    with pytest.raises(ServiceError, match="jeepney"):
        PkgForgeService().start()


def test_double_start_rejected(monkeypatch: pytest.MonkeyPatch):
    svc = PkgForgeService()
    monkeypatch.setattr(svc, "is_running", lambda: True)
    with pytest.raises(ServiceError, match="zaten"):
        svc.start()


# --- live session-bus integration (skipped when unavailable) -----------------

def _session_bus_present() -> bool:
    return bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS"))


@pytest.mark.skipif(
    not (dbus_service.is_available() and _session_bus_present()),
    reason="jeepney or a session bus is unavailable",
)
def test_live_roundtrip_over_session_bus() -> None:
    bus_name = f"org.pkgforge.Test{uuid.uuid4().hex[:8]}"
    svc = PkgForgeService(bus_name=bus_name)
    svc.start()
    try:
        from jeepney import DBusAddress, new_method_call
        from jeepney.io.blocking import open_dbus_connection

        client = open_dbus_connection()
        call = new_method_call(
            DBusAddress(dbus_service.OBJECT_PATH, bus_name=bus_name,
                        interface=dbus_service.INTERFACE),
            "Call", "ss", ("app.version", "{}"),
        )
        # Poll briefly until the name is fully owned and callable.
        last_exc: Exception | None = None
        for _ in range(20):
            try:
                reply = client.send_and_get_reply(call)
                break
            except Exception as exc:  # noqa: BLE001 — retry until name lands
                last_exc = exc
                import time

                time.sleep(0.15)
        else:
            raise AssertionError(f"D-Bus call never succeeded: {last_exc}")

        payload = json.loads(reply.body[0])
        assert payload["result"]["name"] == "PkgForge"
    finally:
        svc.stop()
