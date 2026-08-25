"""Tur-30 — dbus_service politika/kimlik/otobus dallari."""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace as NS

import pytest

import core.dbus_service as DS

# --- is_available ---------------------------------------------------------------

def test_is_available_without_jeepney(monkeypatch):
    monkeypatch.setitem(sys.modules, "jeepney", None)
    assert DS.is_available() is False                 # 30-31


def test_is_available_with_jeepney():
    assert DS.is_available() is True                   # jeepney kurulu


# --- _handle_call ---------------------------------------------------------------

def test_handle_parse_error(monkeypatch):
    monkeypatch.setattr("core.api_server._dispatch",
                        lambda m: {"ok": True})
    yanit = json.loads(DS._handle_call("app.version", "{bozuk"))
    assert yanit["error"]["code"] == -32700            # 70-71


def test_handle_non_dict_params(monkeypatch):
    monkeypatch.setattr("core.api_server._dispatch", lambda m: {"ok": True})
    yanit = json.loads(DS._handle_call("app.version", '"dizi"'))
    assert "error" not in yanit                        # 73-74


def test_handle_write_policy_off(monkeypatch):
    monkeypatch.setattr(DS, "_mutations_allowed", lambda: False)
    yanit = json.loads(DS._handle_call("settings.set", "{}"))   # 77-83
    assert yanit["error"]["code"] == -32000
    assert "salt-okunur" in yanit["error"]["message"]


def test_handle_write_uid_mismatch(monkeypatch):
    monkeypatch.setattr(DS, "_mutations_allowed", lambda: True)
    monkeypatch.setattr(DS, "_own_uid", lambda: 1000)
    yanit = json.loads(DS._handle_call("settings.set", "{}",
                                       caller_uid=1337))         # 84-90
    assert yanit["error"]["code"] == -32002


def test_handle_write_allowed_dispatches(monkeypatch):
    monkeypatch.setattr(DS, "_mutations_allowed", lambda: True)
    monkeypatch.setattr(DS, "_own_uid", lambda: 1000)
    yakalanan = {}
    monkeypatch.setattr("core.api_server._dispatch",
                        lambda m: yakalanan.setdefault("istek", m))
    DS._handle_call("settings.set", '{"a":1}', caller_uid=1000)  # 91-93
    assert yakalanan["istek"]["method"] == "settings.set"


def test_handle_unknown_method_dispatched(monkeypatch):
    monkeypatch.setattr("core.api_server._dispatch",
                        lambda m: {"yontem": m["method"]})
    ham = DS._handle_call("hic.birsey", "{}")          # 94-96
    assert isinstance(ham, str)


# --- _caller_uid ----------------------------------------------------------------

class SahteConn:
    def __init__(self, cevap=None, hata=None):
        self.cevap = cevap
        self.hata = hata

    def send_and_get_reply(self, call):
        if self.hata:
            raise self.hata
        return self.cevap


def test_caller_uid_none_when_no_sender():
    assert DS._caller_uid(SahteConn(), "") is None     # 107-108


def test_caller_uid_success():
    conn = SahteConn(NS(body=[1000]))
    assert DS._caller_uid(conn, ":1.5") == 1000        # 117


def test_caller_uid_failure_returns_none():
    conn = SahteConn(hata=RuntimeError("surucu yok"))
    assert DS._caller_uid(conn, ":1.5") is None        # 118-119


# --- start / stop ---------------------------------------------------------------

def test_start_connect_failure_wrapped(monkeypatch):
    servis = DS.PkgForgeService()

    def patla():
        raise RuntimeError("veriyolu kapali")
    monkeypatch.setitem(sys.modules, "jeepney.io.blocking",
                        NS(open_dbus_connection=patla))
    with pytest.raises(DS.ServiceError, match="bağlanılamadı"):   # 149-150
        servis.start()


def test_start_name_request_rejected(monkeypatch):
    servis = DS.PkgForgeService()

    class SahteConn2:
        def __init__(self):
            self.kapandi = False

        def send_and_get_reply(self, call):
            return NS(header=NS(message_type="hatali-tip"),
                      body=["meşgul"])

        def close(self):
            self.kapandi = True

    baglanti = SahteConn2()
    monkeypatch.setitem(sys.modules, "jeepney.io.blocking",
                        NS(open_dbus_connection=lambda: baglanti))
    # start() icindeki 'from jeepney import MessageType' gercek modulu
    # okur; method_return'a rastgele bir nesne verip yaniti eslestirmez.
    monkeypatch.setitem(sys.modules, "jeepney",
                        NS(DBusNameFlags=NS(do_not_queue=4),
                           MessageType=NS(method_return="gercek-donus")))
    monkeypatch.delitem(sys.modules, "jeepney.messaging", raising=False)

    with pytest.raises(DS.ServiceError, match="Veriyolu adı alınamadı"):
        servis.start()
    assert baglanti.kapandi is True                    # 154-158


def test_stop_oserror_swallowed():
    servis = DS.PkgForgeService()

    class KirikConn:
        def close(self):
            raise OSError("zaten kapali")
    servis._conn = KirikConn()
    servis.stop()                                      # 213-215
    assert servis.is_running() is False

# --- sync_backends ----------------------------------------------------------------

import core.sync_backends as SBC
from core.sync_backends import GitBackend, RcloneBackend


def test_age_encrypt_paths(monkeypatch):
    monkeypatch.setattr(SBC.shutil, "which", lambda n: None)
    with pytest.raises(SBC.SyncBackendError, match="kurulu degil"):
        SBC.age_encrypt(b"x", "anahtar")               # 33-34

    monkeypatch.setattr(SBC.shutil, "which", lambda n: "/usr/bin/age")
    with pytest.raises(SBC.SyncBackendError, match="recipient"):
        SBC.age_encrypt(b"x", "")                      # 35-36

    monkeypatch.setattr(SBC.subprocess, "run",
                        lambda *a, **k: NS(returncode=0, stdout=b"sifreli",
                                           stderr=b""))
    assert SBC.age_encrypt(b"veri", "anahtar") == b"sifreli"   # 37-42

    monkeypatch.setattr(SBC.subprocess, "run",
                        lambda *a, **k: NS(returncode=2, stdout=b"",
                                           stderr=b"kotu anahtar"))
    with pytest.raises(SBC.SyncBackendError, match="sifreleme basarisiz"):
        SBC.age_encrypt(b"veri", "kotu")               # 40-41


def test_age_decrypt_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(SBC.shutil, "which", lambda n: None)
    with pytest.raises(SBC.SyncBackendError, match="kurulu degil"):
        SBC.age_decrypt(b"x", tmp_path / "kimlik")     # 47-48

    monkeypatch.setattr(SBC.shutil, "which", lambda n: "/usr/bin/age")
    with pytest.raises(SBC.SyncBackendError, match="identity"):
        SBC.age_decrypt(b"x", tmp_path / "yok.key")    # 50-51

    kimlik = tmp_path / "kimlik.key"
    kimlik.write_text("AGE-SECRET-KEY-1")
    monkeypatch.setattr(SBC.subprocess, "run",
                        lambda *a, **k: NS(returncode=0, stdout=b"acik",
                                           stderr=b""))
    assert SBC.age_decrypt(b"sifreli", kimlik) == b"acik"      # 52-57

    monkeypatch.setattr(SBC.subprocess, "run",
                        lambda *a, **k: NS(returncode=5, stdout=b"",
                                           stderr=b"bozuk blob"))
    with pytest.raises(SBC.SyncBackendError, match="cozme basarisiz"):
        SBC.age_decrypt(b"x", kimlik)                  # 55-56


def test_backend_unavailable_guards():
    temel = SBC.SyncBackend()
    assert temel.is_available() is False               # 68

    git = GitBackend(repo_url="")
    with pytest.raises(SBC.SyncBackendError, match="git kurulu degil ya da repo_url bos"):
        git.pull("main")                               # 107-108

    rclone = RcloneBackend(remote="")
    with pytest.raises(SBC.SyncBackendError, match="rclone kurulu degil ya da remote bos"):
        rclone.push(b"x", "yedek")                     # 134-135


def test_run_failure_wrapped(monkeypatch):
    monkeypatch.setattr(SBC.subprocess, "run",
                        lambda *a, **k: NS(returncode=128, stderr="fatal: yok"))
    with pytest.raises(SBC.SyncBackendError, match="basarisiz"):   # 166-168
        SBC._run(["git", "pull", "origin"])