"""Tur-45 — api_server ve compat son savunma satirlari."""
from __future__ import annotations

import os
import select
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS

import core.api_server as AS
import core.compatibility_checker as CC

ARACLAR = NS(bsdtar="bsdtar", file_cmd="file", readelf="readelf",
             objdump="objdump", ldd="ldd", pacman="pacman", namcap="namcap")


# --- 792: kalici depo sentinel'i -------------------------------------------------

def test_restore_queue_false_sentinel(monkeypatch):
    monkeypatch.setattr(AS, "_queue_items", {})
    monkeypatch.setattr(AS, "_queue_seq", 0)
    monkeypatch.setattr(AS, "_queue_store", False)   # denendi-ve-basarısız
    assert AS.restore_queue() == 0                    # 791-792


# --- 1049: gecerli last_run hesabi -----------------------------------------------

def test_scheduler_tick_valid_last_run(monkeypatch):
    olaylar = []
    monkeypatch.setattr(AS, "_event", lambda m, p: olaylar.append(p))
    ayarlar = {}
    monkeypatch.setattr(AS, "load_settings", lambda: dict(ayarlar))
    monkeypatch.setattr(AS, "save_settings", lambda s: ayarlar.update(s))
    # son calisma 10 saat once -> due
    eski = time.strftime("%Y-%m-%d %H:%M:%S",
                         time.localtime(time.time() - 10 * 3600))
    durum = {"enabled": True, "last_run": eski, "interval_hours": 2,
             "task": "bakim"}
    monkeypatch.setattr(AS, "_schedule_state", lambda: dict(durum))

    cagri = {"n": 0}

    def tek_tur(sn):
        cagri["n"] += 1
        raise KeyboardInterrupt
    monkeypatch.setattr(time, "sleep", tek_tur)
    try:
        AS._scheduler_tick()
    except KeyboardInterrupt:
        pass
    assert ayarlar.get("schedule_last_run")
    assert any(o.get("task") == "bakim" for o in olaylar)          # 1047-1051


# --- 1344-1348: bozuk->gecerli->EOF tam dongu -------------------------------------

def test_serve_parse_continue_then_dispatch(monkeypatch):
    satirlar = ["{", '{"id": 9, "method": "app.version"}', ""]
    gonderilen = []
    hatalar = []

    class SahteStdin:
        def readline(self):
            return satirlar.pop(0) if satirlar else ""

    monkeypatch.setattr(sys, "stdin", SahteStdin())
    monkeypatch.setattr(select, "select",
                        lambda *a: ([sys.stdin], [], []))
    monkeypatch.setattr(AS, "_send", lambda o: gonderilen.append(o))
    monkeypatch.setattr(AS, "_error",
                        lambda rid, kod, msg: hatalar.append(kod))
    monkeypatch.setattr(AS, "_ensure_qapp",
                        lambda: NS(processEvents=lambda: None))

    AS.serve()                                                     # 1344-1348
    assert hatalar == [-32700]                                     # 1345-1347
    assert len(gonderilen) == 1 and gonderilen[0]["id"] == 9       # 1348


# --- 1608-1611: serve_forever KI + server_close -----------------------------------

def test_serve_http_keyboard_interrupt_cleanup(monkeypatch):
    kapandi = {"evet": False}

    class SahteSunucu:
        def __init__(self, adres, handler):
            pass

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            kapandi["evet"] = True

    monkeypatch.setattr("http.server.ThreadingHTTPServer", SahteSunucu)
    eski = (AS._ensure_qapp, AS._ensure_scheduler, AS.restore_queue)
    AS._ensure_qapp = lambda: None
    AS._ensure_scheduler = lambda: None
    AS.restore_queue = lambda: 0
    try:
        AS.serve_http(port=1, token="t", host="127.0.0.1")          # 1607-1611
    finally:
        AS._ensure_qapp, AS._ensure_scheduler, AS.restore_queue = eski
    assert kapandi["evet"] is True


# --- compat 391-392: symlink ebeveyn ile dizin-disi kacis -------------------------

def test_shared_libs_symlink_escape(tmp_path, monkeypatch):
    dis_dizin = tmp_path / "dis"
    dis_dizin.mkdir()
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")

    def sahte(cmd, timeout=0, **k):
        if "-tf" in cmd:
            return NS(returncode=0, stdout="bag/x.so\n", stderr="")
        if "-xf" in cmd:
            hedef = Path(cmd[cmd.index("-C") + 1])
            bag = hedef / "bag"
            os.symlink(dis_dizin, bag)      # arsiv uyesi sembolik kacis
            (dis_dizin / "x.so").write_bytes(b"ELFx")
            return NS(returncode=0, stdout="", stderr="")
        if "--mime-type" in cmd:
            return NS(returncode=0, stdout="application/x-sharedlib",
                      stderr="")
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(CC, "safe_run", sahte)
    monkeypatch.setattr(CC, "_system_lib_sonames", lambda: set())
    monkeypatch.setattr(CC, "_get_system_glibc", lambda t: "")
    r = CC._check_shared_libraries(pkg, ARACLAR)                   # 389-392
    assert r.severity == CC.CheckSeverity.PASS   # hicbiri analiz edilmedi
