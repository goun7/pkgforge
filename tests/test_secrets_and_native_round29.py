"""Tur-29 — secrets_store dbus yollari ve native son dort satiri."""
from __future__ import annotations

import subprocess
from types import SimpleNamespace as NS

import pytest

import core.native_deb_converter as ND
import core.secrets_store as SS
from core.native_deb_converter import NativeDebConverter

# --- secrets_store ---------------------------------------------------------------

class SahteBaglanti:
    """jeepney blocking connection taklidi; cagri adina gore davranir."""

    def __init__(self, davranis):
        self.davranis = davranis          # callable(str)->cevap
        self.kapandi = False

    def send_and_get_reply(self, call):
        return self.davranis(repr(call))

    def close(self):
        self.kapandi = True


def _bus_cevresi(monkeypatch, conn):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/sahte")
    jeepney_mod = NS()
    bus_mod = NS(message_bus=NS(NameHasOwner=lambda s: NS()))
    io_mod = NS(open_dbus_connection=lambda: conn)
    monkeypatch.setitem(__import__("sys").modules,
                        "jeepney.bus_messages", bus_mod)
    monkeypatch.setitem(__import__("sys").modules,
                        "jeepney.io.blocking", io_mod)
    return jeepney_mod


def test_bus_has_service_true(monkeypatch):
    conn = SahteBaglanti(lambda s: NS(body=[True]))
    _bus_cevresi(monkeypatch, conn)
    assert SS.bus_has_service() is True and conn.kapandi is True


def test_bus_has_service_send_failure(monkeypatch):
    def patla(s):
        raise RuntimeError("otobus koptu")
    conn = SahteBaglanti(patla)
    _bus_cevresi(monkeypatch, conn)
    assert SS.bus_has_service() is False and conn.kapandi is True


def test_bus_has_service_close_oserror_swallowed(monkeypatch):
    conn = SahteBaglanti(lambda s: NS(body=[False]))

    def patla():
        raise OSError("zaten kapali")
    conn.close = patla
    _bus_cevresi(monkeypatch, conn)
    assert SS.bus_has_service() is False              # 48-49


def test_bus_without_env_or_lib(monkeypatch):
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    assert SS.bus_has_service() is False              # 34-35


class _Cagri:
    def __init__(self, etiket):
        self.etiket = etiket


def _etiketli_conn(adimlar):
    """adimlar: {metot_adi: cevap|Exception}"""
    conn = SahteBaglanti(None)

    def davranis(s):
        for anahtar, deger in adimlar.items():
            if anahtar in s:
                if isinstance(deger, Exception):
                    raise deger
                return deger
        raise AssertionError(f"beklenmeyen cagri: {s[:80]}")

    conn.davranis = davranis
    return conn


def test_create_item_error_wrapped(monkeypatch, tmp_path):
    conn = _etiketli_conn({
        "OpenSession": NS(body=[NS(), "/oturum"]),
        "SearchItems": NS(body=[[], []]),
        "CreateItem": RuntimeError("redd"),
    })
    magaza = SS.SecretStore(attributes={"kullanici": "a"})
    monkeypatch.setattr(SS.SecretStore, "_conn", lambda self: conn)
    with pytest.raises(SS.SecretStoreError, match="CreateItem"):
        magaza.set_secret("gizli")                    # 153-154 + 191-193


def test_get_secret_error_wrapped(monkeypatch):
    conn = _etiketli_conn({
        "OpenSession": NS(body=[NS(), "/oturum"]),
        "SearchItems": NS(body=[["/item/1"], []]),
        "GetSecret": RuntimeError("kopuk"),
    })
    magaza = SS.SecretStore(attributes={"kullanici": "a"})
    monkeypatch.setattr(SS.SecretStore, "_conn", lambda self: conn)
    with pytest.raises(SS.SecretStoreError, match="GetSecret"):
        magaza.get_secret()                           # 169-170 + 205-208


# --- native son dort satiri ------------------------------------------------------

class _NDSurec:
    def __init__(self, rc):
        self.stdout = NS(close=lambda: None)
        self.stderr = NS(read=lambda: b"hata-akisi")
        self.returncode = rc

    def wait(self, timeout=0):
        return 0

    def communicate(self, timeout=0):
        return (b"", b"cikarilamadi")


def test_extract_returncode_failures(monkeypatch, tmp_path):
    nd = NativeDebConverter.__new__(NativeDebConverter)
    ND.QObject.__init__(nd)
    nd._tools = NS(ar="/usr/bin/ar", bsdtar="/usr/bin/bsdtar")
    deb = tmp_path / "x.deb"
    deb.write_bytes(b"D")
    monkeypatch.setattr(ND, "safe_run",
                        lambda *a, **k: NS(returncode=0,
                                           stdout="data.tar.xz\n"))

    def ar_kirik(cmd, *a, **k):
        return _NDSurec(2) if cmd[:2] == [str(nd._tools.ar), "p"] \
            else _NDSurec(0)
    monkeypatch.setattr(subprocess, "Popen", ar_kirik)
    with pytest.raises(RuntimeError, match=r"ar başarısız \(kod"):   # 155-158
        nd._extract_data_tar(deb, tmp_path)

    def tar_kirik(cmd, *a, **k):
        return _NDSurec(3) if "-xf" in cmd else _NDSurec(0)
    monkeypatch.setattr(subprocess, "Popen", tar_kirik)
    with pytest.raises(RuntimeError, match="İçerik çıkarılamadı"):  # 160
        nd._extract_data_tar(deb, tmp_path)


def test_cancel_running_process(qapp):
    nd = NativeDebConverter.__new__(NativeDebConverter)
    ND.QObject.__init__(nd)
    nd._cancelled = False
    yakalanan = []
    nd.output_line = NS(emit=lambda m: yakalanan.append(m))
    calisiyor = object()                              # NotRunning'dan farkli
    nd._process = NS(state=lambda: calisiyor, kill=lambda: yakalanan.append("kill"))
    nd.cancel()                                       # 110-111
    assert yakalanan == ["kill", "⚠ Native DEB dönüşümü iptal edildi"]

@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def test_set_get_happy_paths(monkeypatch):
    conn = _etiketli_conn({
        "OpenSession": NS(body=[NS(), "/oturum"]),
        "SearchItems": NS(body=[["/item/eski"], []]),
        "DeleteItem": NS(body=["/item/eski"]),
        "CreateItem": NS(body=["/item/yeni", "/"]),
        "GetSecret": NS(body=[("/oturum", b"", b"buyuk-sir", "text/plain")]),
    })
    magaza = SS.SecretStore(attributes={"kullanici": "a"})
    monkeypatch.setattr(SS.SecretStore, "_conn", lambda self: conn)

    magaza.set_secret("yeni-sir")                     # 181-188 + 191-193
    assert conn.kapandi is True

    conn.kapandi = False
    assert magaza.get_secret() == "buyuk-sir"         # 199-203 + 205-208


def test_set_get_close_oserror_swallowed(monkeypatch):
    set_conn = _etiketli_conn({
        "OpenSession": NS(body=[NS(), "/oturum"]),
        "SearchItems": NS(body=[[], []]),
        "CreateItem": NS(body=["/item/y", "/"]),
    })
    get_conn = _etiketli_conn({
        "OpenSession": NS(body=[NS(), "/oturum2"]),
        "SearchItems": NS(body=[["/item/1"], []]),
        "GetSecret": NS(body=[("/oturum2", b"", b"s", "text/plain")]),
    })

    def patla():
        raise OSError("kapama hatasi")
    set_conn.close = patla
    get_conn.close = patla
    magaza = SS.SecretStore(attributes={"kullanici": "a"})
    monkeypatch.setattr(SS.SecretStore, "_conn",
                        lambda self: set_conn if not magaza_kayit else get_conn)
    magaza_kayit = {"tur": ""}

    def sec(self):
        return get_conn if magaza_kayit["tur"] == "get" else set_conn
    monkeypatch.setattr(SS.SecretStore, "_conn", sec)

    magaza_kayit["tur"] = "set"
    magaza.set_secret("deger")                        # 191-193
    magaza_kayit["tur"] = "get"
    assert magaza.get_secret() == "s"                 # 205-208