"""Tur-48 — cve_scanner ve dbus_service kalan satirlari."""
from __future__ import annotations

import json
import sys
import threading
from types import SimpleNamespace as NS

import pytest
from jeepney import HeaderFields, MessageType

import core.cve_scanner as CS
import core.dbus_service as DS

# --- cve 44-46: bozuk OSV yaniti ---------------------------------------------------

def test_query_osv_bad_json(monkeypatch):
    class SahteYanit:
        def read(self):
            return b"{bozuk-json"
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    def sahte_urlopen(req, timeout=0):
        return SahteYanit()
    import core.cve_scanner as mod
    monkeypatch.setattr(mod.urllib.request, "urlopen", sahte_urlopen)
    assert CS._query_osv("demo") == []                            # 44-46


def test_query_osv_missing_key(monkeypatch):
    class SahteYanit:
        def read(self):
            return json.dumps({"baska": 1}).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    monkeypatch.setattr(CS.urllib.request, "urlopen",
                        lambda req, timeout=0: SahteYanit())
    assert CS._query_osv("demo", timeout=1) == []                 # 44-46


def test_scan_package_analyzer_paths(tmp_path, monkeypatch):
    pkg = tmp_path / "paket-1-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"P")
    pa = sys.modules.setdefault("core.package_analyzer", NS())

    # analiz basarili (129-132, 137-139)
    monkeypatch.setattr(pa, "analyze_package",
                        lambda p, t: NS(depends=("glibc", "openssl")),
                        raising=False)
    monkeypatch.setattr(CS, "scan_dependencies",
                        lambda deps, offline=False:
                        {"vulns": [], "scanned": len(deps)})
    sonuc = CS.scan_package(pkg, None)
    assert sonuc["package"] == "paket-1-1-x86_64.pkg.tar.zst"     # 138-139
    assert sonuc["scanned"] == 2

    # analyzer istisnasi (133-135)
    def patlak(p, t):
        raise ValueError("arsiv bozuk")
    monkeypatch.setattr(pa, "analyze_package", patlak, raising=False)
    kayit = []
    monkeypatch.setattr(CS.log, "warning",
                        lambda m, *a: kayit.append(m), raising=False)
    sonuc2 = CS.scan_package(pkg, None)
    assert sonuc2["scanned"] == 0                                 # deps=[]
    assert any("analiz edilemedi" in m for m in kayit)


# --- dbus 102, 193-205, 225-240 -----------------------------------------------------

def test_own_uid_real():
    import os
    assert DS._own_uid() == os.getuid()                           # 102


class _SahteDbusSurec:
    """_serve_loop icin minimal mesaj pompasi."""
    NotRunning = 0

    def __init__(self, svc):
        self._svc = svc

    def state(self):
        return self.NotRunning

    def kill(self):
        pass


def test_serve_loop_uid_fail_and_handler_error(monkeypatch):
    """193-194 uid-istisnasi + 198-201 handler-istisnasi + 204-205 OSError."""
    svc = DS.PkgForgeService.__new__(DS.PkgForgeService)
    yakalanan = {}
    kapanan = {"n": 0}
    cagri = {"recv": 0}

    from collections import deque
    mesaj = NS(header=NS(message_type=MessageType.method_call,
                         fields={HeaderFields.sender: ":1.5",
                                 HeaderFields.member: "Call"}),
               body=["health.check", "{}"], serial=7)

    class KopanBaglanti:
        def filter(self, rule):
            return NS(queue=deque([mesaj]), close=self.close)
        def send_message(self, msg):
            pass
        def recv_messages(self, timeout=None):
            cagri["recv"] += 1
            if cagri["recv"] == 1:
                raise TimeoutError                                 # 180-181
            if cagri["recv"] >= 3:
                raise OSError("baglanti kapandi")                 # 204-205
        def close(self):
            kapanan["n"] += 1

    svc._conn = KopanBaglanti()
    svc._stop = threading.Event()

    monkeypatch.setattr(DS, "_caller_uid",
                        lambda conn, sender: (_ for _ in ()).throw(
                            RuntimeError("uid alinamadi")))       # -> 193-194

    def patlak(method, params, caller_uid=None):
        raise RuntimeError("isleyici patladi")
    monkeypatch.setattr(DS, "_handle_call", patlak)               # -> 198-201

    # _serve_loop fonksiyon icinde 'from jeepney import new_method_return'
    # yaptigi icin dogrudan jeepney modulune yama gerekir.
    monkeypatch.setattr("jeepney.new_method_return",
                        lambda msg, imza, deger: yakalanan.setdefault(
                            "deger", deger[0]))

    svc._serve_loop()                                             # 169-207
    payload = json.loads(yakalanan["deger"])
    assert payload["error"]["code"] == -32000                     # 199-201
    assert kapanan["n"] >= 1                                      # 206-207 finally


def test_start_stop_default_lifecycle(monkeypatch):
    olusturulan = []

    class SahteServis:
        def __init__(self):
            self.durdu = False
            olusturulan.append(self)
        def is_running(self):
            return not self.durdu and self is olusturulan[-1]
        def start(self):
            pass
        def stop(self):
            self.durdu = True

    monkeypatch.setattr(DS, "PkgForgeService", SahteServis)
    monkeypatch.setattr(DS, "_service", None)

    sonuc = DS.start_default()                                    # 228-231
    assert sonuc == {"started": True,
                     "bus_name": DS.DEFAULT_BUS_NAME}

    with pytest.raises(DS.ServiceError):
        DS.start_default()                                        # 226-227

    durus = DS.stop_default()                                     # 236-240
    assert durus == {"stopped": True}
    assert DS._service is None

    # servis yokken stop_default yine {"stopped": True} doner (237 dal atlanir)
    assert DS.stop_default() == {"stopped": True}