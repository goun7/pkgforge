"""Faz 3 (Alan C) sidecar handler tests — profile.* (C2)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _rpc(proc, method, params=None, req_id=1):
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("sidecar closed stdout")
        data = json.loads(line)
        if data.get("id") == req_id:
            return data


@pytest.fixture
def sidecar(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env.pop("XDG_CONFIG_HOME", None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, env=env,
        cwd=str(PROJECT_ROOT),
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# --- C2: profile.* ----------------------------------------------------------

def test_profile_current_defaults(sidecar):
    resp = _rpc(sidecar, "profile.current")
    assert resp["result"]["name"] == "default"


def test_profile_list_has_default(sidecar):
    resp = _rpc(sidecar, "profile.list")
    assert {"name": "default", "active": True} in resp["result"]


def test_profile_create_switch_list(sidecar):
    assert "result" in _rpc(sidecar, "profile.create", {"name": "work"})
    resp = _rpc(sidecar, "profile.switch", {"name": "work"}, req_id=2)
    assert resp["result"]["name"] == "work"

    listing = _rpc(sidecar, "profile.list", req_id=3)["result"]
    assert {"name": "work", "active": True} in listing
    assert {"name": "default", "active": False} in listing


def test_profile_settings_follow_switch(sidecar):
    # Set a marker in default, switch to a fresh profile, verify isolation.
    cur = _rpc(sidecar, "settings.get")["result"]
    cur["theme"] = "light"
    _rpc(sidecar, "settings.set", cur, req_id=2)

    _rpc(sidecar, "profile.create", {"name": "iso"}, req_id=3)
    _rpc(sidecar, "profile.switch", {"name": "iso"}, req_id=4)

    fresh = _rpc(sidecar, "settings.get", req_id=5)["result"]
    assert fresh.get("theme") != "light"


def test_profile_create_duplicate_fails(sidecar):
    _rpc(sidecar, "profile.create", {"name": "dup"})
    resp = _rpc(sidecar, "profile.create", {"name": "dup"}, req_id=2)
    assert resp["error"]["code"] == -32000


def test_profile_delete_default_fails(sidecar):
    resp = _rpc(sidecar, "profile.delete", {"name": "default"})
    assert resp["error"]["code"] == -32000


def test_profile_invalid_name_fails(sidecar):
    for bad in ["../escape", "", "a/b"]:
        resp = _rpc(sidecar, "profile.create", {"name": bad})
        assert resp["error"]["code"] == -32000

# --- C3: sync.* -------------------------------------------------------------

def test_sync_export_creates_bundle(sidecar):
    # ensure there is something to back up
    cur = _rpc(sidecar, "settings.get")["result"]
    cur["theme"] = "dark"
    _rpc(sidecar, "settings.set", cur, req_id=2)

    resp = _rpc(sidecar, "sync.export", req_id=3)
    assert resp["result"]["ok"] is True
    assert Path(resp["result"]["path"]).is_file()


def test_sync_import_missing_file_fails(sidecar):
    resp = _rpc(sidecar, "sync.import", {"backup_path": "/nonexistent.zip"}, req_id=2)
    assert resp["error"]["code"] == -32000


def test_sync_config_stores_url(sidecar):
    _rpc(sidecar, "sync.config",
         {"sync_url": "https://cloud.example/dav/", "sync_username": "u"}, req_id=1)
    got = _rpc(sidecar, "settings.get", req_id=2)["result"]
    assert got["sync_url"] == "https://cloud.example/dav/"
    assert got["sync_username"] == "u"


# --- C1: dbus.* ---------------------------------------------------------------

def test_dbus_status_shape(sidecar):
    resp = _rpc(sidecar, "dbus.status")
    res = resp["result"]
    assert set(res) == {"available", "running", "bus_name"}
    assert res["bus_name"] == "org.pkgforge.App"
    assert isinstance(res["available"], bool)
    assert res["running"] is False


def test_dbus_start_starts_service(sidecar):
    import core.dbus_service as d

    if not d.is_available() or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        pytest.skip("jeepney or session bus unavailable")

    assert _rpc(sidecar, "dbus.start")["result"]["started"] is True

    def _read_until_done():
        for _ in range(20):
            line = sidecar.stdout.readline()
            data = json.loads(line)
            if data.get("method") == "event/dbus_done":
                return data["params"]
        raise AssertionError("dbus_done event never arrived")

    params = _read_until_done()
    assert params["ok"] is True, params

    status = _rpc(sidecar, "dbus.status", req_id=99)["result"]
    assert status["running"] is True
