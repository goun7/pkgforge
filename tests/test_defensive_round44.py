"""Tur-44 — api_server savunma satirlari ve compat symlink kacisi."""
from __future__ import annotations

import queue as queue_mod
import socket
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.api_server as AS


@pytest.fixture()
def senkron_yardimci(monkeypatch):
    kayit = []

    def sahte(fn, event_name="event/x"):
        try:
            kayit.append((event_name, {"ok": True, "sonuc": fn()}))
        except Exception as exc:                                # noqa: BLE001
            kayit.append((event_name, {"ok": False, "hata": str(exc)}))

    monkeypatch.setattr(AS, "_run_thread", sahte)
    monkeypatch.setattr(AS, "_event",
                        lambda m, p: kayit.append(("olay:" + m, p)))
    return kayit

ARACLAR = NS(bsdtar="bsdtar", file_cmd="file", readelf="readelf",
             objdump="objdump", ldd="ldd", pacman="pacman", namcap="namcap")


# --- _run_thread gercek yol ------------------------------------------------------

def test_run_thread_real_paths(monkeypatch):
    olaylar = []
    monkeypatch.setattr(AS, "_event", lambda m, p: olaylar.append((m, p)))

    AS._run_thread(lambda: {"tamam": 1}, "event/t1")               # 252-257
    AS._run_thread(lambda: (_ for _ in ()).throw(
        RuntimeError("is patladi")), "event/t2")                   # 256-257
    son = time.time() + 2.0
    while len(olaylar) < 2 and time.time() < son:
        time.sleep(0.02)
    assert olaylar[0][1]["ok"] is True and olaylar[0][1]["result"] ==         {"tamam": 1}
    assert olaylar[1][1]["ok"] is False and "patladi" in olaylar[1][1]["error"]

    # takma ad dogrudan
    yakalanan = []
    monkeypatch.setattr(AS, "_run_thread",
                        lambda fn, ev: yakalanan.append((fn, ev)))
    AS._run_security_thread(lambda: 1)                             # 262-264
    assert yakalanan[0][1] == "event/security_done"


# --- source_generate build-system dallari ----------------------------------------

def test_source_generate_all_build_systems(senkron_yardimci, monkeypatch,
                                           tmp_path):
    kayit = senkron_yardimci
    fs = sys.modules.setdefault("core.from_source", NS())
    sec = sys.modules.setdefault("core.security", NS())
    monkeypatch.setattr(sec, "safe_run",
                        lambda cmd, timeout=0, **k:
                        NS(returncode=0, stdout="", stderr=""),
                        raising=False)

    def uretici(dosya):
        def sahte(name, url, bs, rd):
            return f"{dosya}:{bs}"
        return sahte
    monkeypatch.setattr(fs, "generate_pkgbuild_from_source",
                        lambda *a: "PKGBUILD", raising=False)

    beklenen = [("meson.build", "meson"), ("Cargo.toml", "cargo"),
                ("configure", "autotools"), ("Makefile", "make"),
                ("makefile", "make"), ("setup.py", "python")]
    for dosya, sistem in beklenen:
        def clone(cmd, timeout=0, __d=dosya, **k):
            repo = Path(cmd[4])
            repo.mkdir(parents=True, exist_ok=True)
            (repo / __d).write_text("")
            return NS(returncode=0, stdout="", stderr="")
        monkeypatch.setattr(sec, "safe_run", clone, raising=False)
        monkeypatch.setattr(fs, "generate_pkgbuild_from_source",
                            uretici(dosya), raising=False)
        AS.handle_source_generate({"repo_url": "https://x/deneme.git",
                                   "output_dir": str(tmp_path)})
        bul = [r for r in kayit if r[0] == "event/source_done"
               and r[1]["ok"]]
        assert bul[-1][1]["sonuc"]["build_system"] == sistem       # 480-490


# --- aur_build install/makepkg-fail/no-pkg dallari --------------------------------

def test_aur_build_install_and_failures(monkeypatch, tmp_path):
    import subprocess as sp

    class Kayit:
        makepkg_cmd = None
    kayit = Kayit()

    def sahte_run(cmd, **k):
        if cmd[:2] == ["git", "clone"]:
            Path(cmd[4]).mkdir(parents=True, exist_ok=True)
            return NS(returncode=0, stderr="")
        if cmd[0] == "makepkg":
            kayit.makepkg_cmd = list(cmd)
            if getattr(kayit, "kirik_makepkg", False):
                return NS(returncode=3, stderr="derleme hatasi")
            if getattr(kayit, "paket_yok", False):
                return NS(returncode=0, stderr="")
            wd = Path(k["cwd"])
            (wd / "cikti.pkg.tar.zst").write_bytes(b"P")
            return NS(returncode=0, stderr="")
        return NS(returncode=0, stderr="")

    monkeypatch.setattr(sp, "run", sahte_run)
    import shutil as shutil_mod
    monkeypatch.setattr(shutil_mod, "which",
                        lambda n: "/usr/bin/pacman" if n == "pacman" else None)

    kayit.kirik_makepkg = False
    kayit.paket_yok = False
    kayitlar = []
    monkeypatch.setattr(AS, "_run_thread",
                        lambda fn, ev="e": kayitlar.append(_calistir(fn)))
    def _calistir(fn):
        try:
            return {"ok": True, "sonuc": fn()}
        except Exception as exc:                                # noqa: BLE001
            return {"ok": False, "hata": str(exc)}

    # install=True -> -si komdu (709)
    AS.handle_aur_build({"name": "demo", "install": True})
    assert kayit.makepkg_cmd[:2] == ["makepkg", "-si"]              # 708-709

    # makepkg hata kodu (714-715)
    kayit.kirik_makepkg = True
    AS.handle_aur_build({"name": "demo"})
    assert "makepkg başarısız" in kayitlar[-1]["hata"]

    # paket dosyasi bulunamadi (717-719)
    kayit.kirik_makepkg = False
    kayit.paket_yok = True
    AS.handle_aur_build({"name": "demo"})
    assert "bulunamadı" in kayitlar[-1]["hata"]


def _calistir(fn):
    try:
        return {"ok": True, "sonuc": fn()}
    except Exception as exc:                                    # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


# --- queue/schedule artiklari ------------------------------------------------------

def test_restore_queue_store_none(monkeypatch):
    monkeypatch.setattr(AS, "_queue_store", None)
    assert AS.restore_queue() == 0                                 # 791-792


def test_dispatch_do_install_serial(monkeypatch):
    monkeypatch.setattr(AS, "_queue_items", {})
    monkeypatch.setattr(AS, "_queue_running", False)
    monkeypatch.setattr(AS, "_queue_lock", __import__("threading").RLock())
    gorunen = []
    class Hazir:
        def stage(self, p):
            pass
        def run_staged(self):
            pass
    monkeypatch.setattr(AS, "_make_pipeline", lambda *a, **k: Hazir())
    monkeypatch.setattr(AS, "_event", lambda m, p: gorunen.append(m))
    AS._queue_items["q1"] = {"id": "q1", "path": "/x", "status": "pending",
                             "priority": 0, "message": ""}
    AS._queue_dispatch(parallel=4, do_install=True)                # 938-940
    assert AS._queue_running is False


def test_schedule_state_real_import():
    durum = AS._schedule_state()                                   # 1003-1006
    assert isinstance(durum, dict) and "enabled" in durum


def test_scheduler_tick_parse_and_outer_error(monkeypatch):
    olaylar = []
    monkeypatch.setattr(AS, "_event", lambda m, p: olaylar.append(p))
    ayarlar = {}
    monkeypatch.setattr(AS, "load_settings", lambda: dict(ayarlar))
    monkeypatch.setattr(AS, "save_settings", lambda s: ayarlar.update(s))

    # bozuk last_run -> due=True dali (1050-1051)
    durum = {"enabled": True, "last_run": "bozuk-format",
             "interval_hours": 1, "task": "t"}
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
    assert any(o.get("task") == "t" for o in olaylar)              # 1047-1051

    # dis istisna -> event/schedule_ran error (1058-1059)
    olaylar.clear()

    def patlak():
        raise RuntimeError("durum okunamadi")
    monkeypatch.setattr(AS, "_schedule_state", patlak)
    try:
        AS._scheduler_tick()
    except KeyboardInterrupt:
        pass
    assert olaylar and "durum okunamadi" in olaylar[0].get("error", "")


# --- serve: hazir-degil continue + gecerli-satir dispatch --------------------------

def test_serve_not_ready_then_valid(monkeypatch):
    satirlar = ['{"id": 5, "method": "app.version"}', ""]
    adim = {"n": 0}

    def sec(*a):
        adim["n"] += 1
        return ([], [], []) if adim["n"] == 1 else ([sys.stdin], [], [])

    class SahteStdin:
        def readline(self):
            return satirlar.pop(0) if satirlar else ""

    gonderilen = []
    monkeypatch.setattr(sys, "stdin", SahteStdin())
    import select as select_mod
    monkeypatch.setattr(select_mod, "select", sec)
    monkeypatch.setattr(AS, "_send",
                        lambda o: gonderilen.append(o)
                        or (_ for _ in ()).throw(KeyboardInterrupt()))
    monkeypatch.setattr(AS, "_ensure_qapp",
                        lambda: NS(processEvents=lambda: None))
    try:
        AS.serve()                                                 # 1336+1347
    except KeyboardInterrupt:
        pass
    assert len(gonderilen) == 1


# --- SSE keepalive dali (gercek sunucu) ---------------------------------------------

def _serbest_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_sse_stream_keepalive_real(monkeypatch):
    """1531-1534: bos kuyruk -> keepalive; ardindan kopma ile 1536-1539."""
    port_cekirdek = _serbest_port()

    class SahteKuyruk(queue_mod.Queue):
        def get(self, timeout=None):
            if not getattr(self, "_bos", False):
                self._bos = True
                raise queue_mod.Empty
            raise OSError("soket kapandi")

    eski = (AS._ensure_qapp, AS._ensure_scheduler, AS.restore_queue)
    AS._ensure_qapp = lambda: None
    AS._ensure_scheduler = lambda: None
    AS.restore_queue = lambda: 0

    import threading
    monkeypatch.setattr(AS.queue, "Queue", SahteKuyruk)

    import http.client

    def kos():
        try:
            AS.serve_http(port=port_cekirdek, token="op", host="127.0.0.1")
        except OSError:
            pass
    threading.Thread(target=kos, daemon=True).start()

    for _ in range(100):
        try:
            c = http.client.HTTPConnection("127.0.0.1", port_cekirdek,
                                           timeout=1)
            c.request("GET", "/health")
            c.getresponse().read()
            c.close()
            break
        except OSError:
            time.sleep(0.05)

    sock = socket.create_connection(("127.0.0.1", port_cekirdek), timeout=10)
    sock.sendall(b"GET /events HTTP/1.1\r\nHost: x\r\n"
                 b"Authorization: Bearer op\r\n\r\n")
    tampon = b""
    son = time.time() + 8
    while time.time() < son and b"keepalive" not in tampon:
        try:
            sock.settimeout(2)
            parca = sock.recv(4096)
        except OSError:
            break
        if not parca:
            break
        tampon += parca
    sock.close()

    AS._ensure_qapp, AS._ensure_scheduler, AS.restore_queue = eski
    assert b"keepalive" in tampon                                 # 1532-1533