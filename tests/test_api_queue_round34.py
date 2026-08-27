"""Tur-34 — api_server kuyruk/zamanlama/profil/senkron/dbus isleyicileri."""
from __future__ import annotations

import sys
import time
from types import SimpleNamespace as NS

import pytest

import core.api_server as AS


@pytest.fixture()
def senkron(monkeypatch):
    kayit = []

    def sahte(fn, event_name="event/x"):
        try:
            kayit.append((event_name, {"ok": True,
                                       "sonuc": fn() if callable(fn) else fn}))
        except Exception as exc:  # noqa: BLE001
            kayit.append((event_name, {"ok": False, "hata": str(exc)}))

    monkeypatch.setattr(AS, "_run_thread", sahte)
    monkeypatch.setattr(AS, "_event", lambda m, p: kayit.append(("olay:" + m, p)))
    return kayit


def _mod(monkeypatch, ad, **ozellikler):
    try:
        mod = __import__(ad, fromlist=["x"])
    except ImportError:
        mod = NS()
        monkeypatch.setitem(sys.modules, ad, mod)
    for k, v in ozellikler.items():
        if hasattr(mod, k):
            monkeypatch.setattr(mod, k, v)
        else:
            monkeypatch.setattr(mod, k, v, raising=False)
    return mod


@pytest.fixture()
def temiz_kuyruk(monkeypatch):
    monkeypatch.setattr(AS, "_queue_items", {})
    monkeypatch.setattr(AS, "_queue_seq", 0)
    monkeypatch.setattr(AS, "_queue_running", False)
    monkeypatch.setattr(AS, "_active_pipelines", {})
    monkeypatch.setattr(AS, "_queue_store", False)   # kalicilik kapali


# --- queue -----------------------------------------------------------------------

def test_queue_add_list_priority_remove_clear(temiz_kuyruk, tmp_path):
    iyi = tmp_path / "a.deb"; iyi.write_bytes(b"A")
    kotu = tmp_path / "b.txt"; kotu.write_text("x")
    yanit = AS.handle_queue_add({"paths": [str(iyi), str(kotu),
                                           str(tmp_path / "yok.rpm"),
                                           str(iyi)]})
    # universal intake: a.deb + b.txt + tekrar a.deb kabul; yok.rpm elenir
    assert yanit == {"added": 3}

    liste = AS.handle_queue_list({})
    assert liste[0]["name"] == "a.deb"

    with pytest.raises(KeyError):
        AS.handle_queue_priority({"id": "q99", "priority": 5})
    assert AS.handle_queue_priority({"id": "q1", "priority": 3})["ok"]

    assert AS.handle_queue_remove({"id": "q1"})["ok"]
    assert AS.handle_queue_remove({"id": "q1"})["ok"]   # tekrar silinmez

    AS.handle_queue_add({"paths": str(iyi)})                      # str form
    assert AS.handle_queue_clear({"status": "pending"})["ok"]
    assert AS.handle_queue_add({"paths": [str(iyi)]})["added"] == 1
    assert AS.handle_queue_clear({})["ok"]
    assert AS.handle_queue_list({}) == []


def test_persist_and_restore(temiz_kuyruk, monkeypatch):
    # store None iken persist'ler sessizce doner
    monkeypatch.setattr(AS, "_queue_store", None)
    AS._persist_item({"id": "q1"}); AS._persist_remove("q1")
    AS._persist_clear(); assert AS.restore_queue() == 0           # 791-792

    class KirilStore:
        def upsert(self, it): raise RuntimeError("yazilamaz")
        def remove(self, iid): raise RuntimeError("silinemez")
        def clear(self, st): raise RuntimeError("temizlenemez")
    monkeypatch.setattr(AS, "_queue_store", KirilStore())
    AS._persist_item({"id": "q1"}); AS._persist_remove("q1")      # 759-760
    AS._persist_clear("")                                         # 779-780
    monkeypatch.setattr(AS, "load_restorable",
                        list, raising=False)
    assert AS.restore_queue() == 0                                # yoksa da

    class Store2(KirilStore):
        def load_restorable(self):
            return [{"id": "q7", "path": "/x.deb", "status": "done"},
                    {"id": "q7", "path": "/x.deb", "status": "done"}]
    monkeypatch.setattr(AS, "_queue_store", Store2())
    assert AS.restore_queue() == 1                                # 802-806
    assert AS._queue_seq == 7 and AS._queue_items["q7"]["id"] == "q7"

    class Store3:
        def load_restorable(self):
            raise RuntimeError("bozuk veritabani")
    monkeypatch.setattr(AS, "_queue_store", Store3())
    assert AS.restore_queue() == 0                                # 795-796


def test_get_queue_store_sentinel(monkeypatch):
    monkeypatch.setattr(AS, "_queue_store", None)

    class Patlak:
        def __init__(self): raise RuntimeError("acilamadi")
    monkeypatch.setitem(sys.modules, "core.queue_store",
                        NS(QueueStore=Patlak))
    assert AS._get_queue_store() is None                          # 749-750

    monkeypatch.setattr(AS, "_queue_store", False)
    assert AS._get_queue_store() is None                          # False->None


def test_get_queue_store_registers_atexit_close(monkeypatch):
    """Singleton QueueStore process cikisinda atexit ile kapatilmali."""
    monkeypatch.setattr(AS, "_queue_store", None)
    kayitli = []
    monkeypatch.setattr(AS.atexit, "register", lambda fn: kayitli.append(fn))

    class SahteStore:
        closed = False

        def close(self):
            SahteStore.closed = True

    monkeypatch.setitem(sys.modules, "core.queue_store",
                        NS(QueueStore=SahteStore))
    store = AS._get_queue_store()
    assert isinstance(store, SahteStore)
    assert len(kayitli) == 1            # atexit'e tam bir kayit
    kayitli[0]()                        # kayitli close cagrisi
    assert SahteStore.closed is True


def test_queue_cancel(temiz_kuyruk):
    iptal = []
    calisan = NS(cancel=lambda: iptal.append(1))
    kirik = NS(cancel=lambda: (_ for _ in ()).throw(RuntimeError("kilit")))
    AS._active_pipelines.update({"q1": calisan, "q2": kirik})
    yanit = AS.handle_queue_cancel({})                            # 968-977
    assert yanit == {"cancelled": 1}
    yanit = AS.handle_queue_cancel({"item_id": "q1"})
    assert yanit["cancelled"] == 1


def test_queue_start_paths(temiz_kuyruk, monkeypatch):
    assert AS.handle_queue_start({})["started"] is False          # bos kuyruk
    AS._queue_items["q1"] = {"id": "q1", "path": "/x", "status": "pending"}
    AS._queue_running = True
    assert AS.handle_queue_start({})["reason"] == "already running"
    AS._queue_running = False
    monkeypatch.setattr(AS, "_queue_dispatch", lambda *a: None)
    yanit = AS.handle_queue_start({"parallel": 9, "install": True})
    assert yanit["started"] is True                               # 992-995
    time.sleep(0.05)
    AS._queue_running = False


# --- schedule / profile ----------------------------------------------------------

def test_schedule_get_set(monkeypatch):
    durumlar = [
        {"enabled": False, "last_run": "", "interval_hours": 2, "task": "t"},
        {"enabled": True, "last_run": "", "interval_hours": 2, "task": "t"},
        {"enabled": True, "last_run": "2024-01-01 10:00:00",
         "interval_hours": 2, "task": "t"},
        {"enabled": True, "last_run": "bozuk", "interval_hours": 2, "task": "t"},
    ]
    for d in durumlar:
        monkeypatch.setattr(AS, "_schedule_state", lambda d=d: dict(d))
        st = AS.handle_schedule_get({})                           # 1009-1024
        assert "next_run" in st

    ayarlar = {}
    monkeypatch.setattr(AS, "load_settings", lambda: dict(ayarlar))
    monkeypatch.setattr(AS, "save_settings",
                        lambda s: ayarlar.update(s))
    assert AS.handle_schedule_set({"enabled": True,
                                   "interval_hours": 0.5,
                                   "task": "guncelle"})["ok"]     # 1027-1036
    assert ayarlar["schedule_interval_hours"] == 1.0              # min 1.0
    assert ayarlar["schedule_task"] == "guncelle"


def test_profile_handlers(monkeypatch):
    pr = _mod(monkeypatch, "core.profiles")
    monkeypatch.setattr(pr, "create_profile", lambda n: {"olusturuldu": n})
    monkeypatch.setattr(pr, "switch_profile", lambda n: {"gecildi": n})
    monkeypatch.setattr(pr, "delete_profile", lambda n: {"silindi": n})

    i18n = _mod(monkeypatch, "i18n")
    monkeypatch.setattr(i18n, "init_language", lambda: None, raising=False)
    assert AS.handle_profile_switch({"name": "oyun"}) ==         {"gecildi": "oyun"}                                       # 1084-1092

    def patlak_dil():
        raise RuntimeError("dil yuklenemedi")
    monkeypatch.setattr(i18n, "init_language", patlak_dil, raising=False)
    assert AS.handle_profile_switch({"name": "oyun"})["gecildi"] == "oyun"

    assert AS.handle_profile_create({"name": "yeni"})["olusturuldu"] == "yeni"
    assert AS.handle_profile_delete({"name": "eski"})["silindi"] == "eski"


# --- sync ------------------------------------------------------------------------

def test_sync_export_import_push_pull(senkron, monkeypatch):
    cs = _mod(monkeypatch, "core.cloud_sync")
    monkeypatch.setattr(cs, "export_backup",
                        lambda out=None: {"yedek": out}, raising=False)
    monkeypatch.setattr(cs, "import_backup",
                        lambda p: {"geri": p}, raising=False)
    assert AS.handle_sync_export({})["yedek"] is None             # 1106
    assert AS.handle_sync_import({"backup_path": "/b.zip"})["geri"] == "/b.zip"

    monkeypatch.setattr(cs, "webdav_push", lambda: {"itti": True},
                        raising=False)
    monkeypatch.setattr(cs, "webdav_pull", lambda: {"cekdi": True},
                        raising=False)
    AS.handle_sync_push({})                                       # 1168
    AS.handle_sync_pull({})                                       # 1175
    assert senkron[-1][1]["sonuc"]["cekdi"] is True


def test_sync_config_password_paths(monkeypatch):
    ayarlar = {}
    monkeypatch.setattr(AS, "load_settings", lambda: dict(ayarlar))
    monkeypatch.setattr(AS, "save_settings", lambda s: ayarlar.clear() or ayarlar.update(s))

    yanit = AS.handle_sync_config({"sync_url": "https://sunucu",
                                   "sync_username": "ali"})
    assert yanit["password_stored"] == "settings"                 # 1133-1136

    ss = _mod(monkeypatch, "core.secrets_store")

    # anahtarlik basarili
    monkeypatch.setattr(ss, "available", lambda: True, raising=False)

    class Depo:
        def __init__(self, user): pass
        def set_secret(self, s): Depo.kayit = s
    Depo.kayit = ""
    monkeypatch.setattr(ss, "webdav_store", Depo, raising=False)
    yanit = AS.handle_sync_config({"sync_username": "ali",
                                   "sync_password": "gizli"})
    assert yanit["password_stored"] == "keyring"                  # 1147-1149
    assert Depo.kayit == "gizli"
    assert "sync_password" not in ayarlar

    # anahtarlik hata verir -> settings'e duser + uyari
    def kirik_depo(user):
        raise RuntimeError("servis yok")
    monkeypatch.setattr(ss, "webdav_store", kirik_depo, raising=False)
    yanit = AS.handle_sync_config({"sync_username": "ali",
                                   "sync_password": "gizli2"})
    assert yanit["password_stored"] == "settings"
    assert "kullanılamadı" in yanit["warning"]                    # 1151

    # kullanici adi yok -> settings + uyari
    yanit = AS.handle_sync_config({"sync_username": "",
                                   "sync_password": "gizli3"})
    assert yanit.get("warning") == "Anahtarlik icin kullanici adi gerekli"


# --- dbus / rehearse -------------------------------------------------------------

def test_dbus_handlers(senkron, monkeypatch):
    ayarlar = {}
    monkeypatch.setattr(AS, "load_settings", lambda: dict(ayarlar))
    monkeypatch.setattr(AS, "save_settings", lambda s: (ayarlar.clear(), ayarlar.update(s)))
    yanit = AS.handle_dbus_set_policy({"allow_mutations": True})   # 1180-1184
    assert yanit["allow_mutations"] is True

    ds = _mod(monkeypatch, "core.dbus_service")
    monkeypatch.setattr(ds, "start_default", lambda: {"ayakta": True},
                        raising=False)
    AS.handle_dbus_start({})                                      # 1191
    assert senkron[-1][1]["sonuc"]["ayakta"] is True


def test_install_rehearse(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="package_path"):
        AS.handle_install_rehearse({})
    ir = _mod(monkeypatch, "core.install_rehearsal")
    monkeypatch.setattr(ir, "rehearse_install",
                        lambda p: {"prova": str(p)}, raising=False)
    yanit = AS.handle_install_rehearse(
        {"package_path": str(tmp_path / "p.deb")})                # 1199-1202
    assert "prova" in yanit

# --- derin bloklar ---------------------------------------------------------------

class SahteSignal:
    def __init__(self):
        self.aboneler = []

    def connect(self, fn, **k):
        self.aboneler.append(fn)


def test_make_pipeline_connections(temiz_kuyruk, monkeypatch):
    from PyQt6.QtCore import QCoreApplication
    _uygulama = QCoreApplication.instance() or QCoreApplication([])

    class SahteBoru:
        def __init__(self):
            self.step_changed = SahteSignal()
            self.progress = SahteSignal()
            self.log_message = SahteSignal()
            self.compatibility_ready = SahteSignal()
            self.finished = SahteSignal()
            self.onaylandi = []
            self._gecildi = False

        def approve_install(self):
            self.onaylandi.append(1)

        def dismiss_install(self, msg=""):
            self._gecildi = True

    monkeypatch.setitem(sys.modules, "core.pipeline",
                        NS(ConversionPipeline=SahteBoru))
    olaylar = []
    monkeypatch.setattr(AS, "_event", lambda m, p: olaylar.append((m, p)))

    AS._queue_items["q1"] = {"id": "q1", "path": "/x", "status": "running"}
    p = AS._make_pipeline("/dizin/paket.deb", "q1")               # 810-859
    assert AS._active_pipelines["q1"] is p
    assert p._skip_install_message.endswith("kurulum atlandı)")

    # finished tetikle -> item done + event
    sonuc = NS(success=True, message="bitti", converted_pkg=None)
    for fn in p.finished.aboneler:
        fn(sonuc)
    assert AS._queue_items["q1"]["status"] == "done"              # 830-833
    assert any(m == "event/finished" for m, _p in olaylar)

    # hata yolu
    AS._queue_items["q1"]["status"] = "running"
    for fn in p.finished.aboneler:
        fn(NS(success=False, message="hata", converted_pkg=None))
    assert AS._queue_items["q1"]["status"] == "error"

    # do_install yolu onay abonesi ekler
    p2 = AS._make_pipeline("/x.rpm", "q2", do_install=True)
    for fn in p2.compatibility_ready.aboneler:
        fn(NS(to_dict=dict))
    assert p2.onaylandi == [1]                                    # 843-844

    # varsayilan yol kapida gecilir
    p.dismiss_install()
    assert p._gecildi is True


def test_queue_dispatch_loop(temiz_kuyruk, monkeypatch):
    AS._queue_items["q1"] = {"id": "q1", "path": "/p/a.deb",
                             "name": "a.deb", "status": "pending",
                             "priority": 0, "message": ""}
    sahne = []

    class Hazir:
        def stage(self, pth):
            sahne.append(str(pth))

        def run_staged(self):
            pass

    monkeypatch.setattr(AS, "_make_pipeline", lambda *a, **k: Hazir())
    olaylar = []
    monkeypatch.setattr(AS, "_event", lambda m, p: olaylar.append((m, p)))
    AS._queue_dispatch(2, do_install=False)                       # 934-961
    assert sahne == ["/p/a.deb"]
    assert AS._queue_items["q1"]["status"] in ("done", "error", "running")
    assert AS._queue_running is False
    assert ("event/queue_done", {"ok": True}) in olaylar


def test_scheduler_tick_and_ensure(monkeypatch):
    monkeypatch.setattr(AS, "_scheduler_started", False)
    cagri = {"n": 0}
    durum = {"enabled": True, "last_run": "", "interval_hours": 1,
             "task": "guncelle"}
    ayarlar = {}
    monkeypatch.setattr(AS, "_schedule_state", lambda: dict(durum))
    monkeypatch.setattr(AS, "load_settings", lambda: dict(ayarlar))
    monkeypatch.setattr(AS, "save_settings", lambda s: ayarlar.update(s))
    olaylar = []
    monkeypatch.setattr(AS, "_event", lambda m, p: olaylar.append(p))

    # tek tur kos: sleep'i kir
    def bir_ve_cik(sn):
        cagri["n"] += 1
        if cagri["n"] >= 1:
            raise KeyboardInterrupt
    monkeypatch.setattr(time, "sleep", bir_ve_cik)
    try:
        AS._scheduler_tick()                                      # 1039-1060
    except KeyboardInterrupt:
        pass
    assert ayarlar.get("schedule_last_run")
    assert olaylar and olaylar[0]["task"] == "guncelle"

    AS._ensure_scheduler()                                        # 1063-1067
    assert AS._scheduler_started is True
    AS._ensure_scheduler()   # ikinci cagri is yapmaz


def test_schedule_timer_and_run(monkeypatch):
    sc = _mod(monkeypatch, "core.scheduler")
    monkeypatch.setattr(sc, "install_timer",
                        lambda interval_hours=None, dry_run=True:
                        {"kuru": dry_run}, raising=False)
    yanit = AS.handle_schedule_timer_install({})                  # 1115-1121
    assert yanit["kuru"] is True
    monkeypatch.setattr(sc, "run_due", lambda force=False: {"zorla": force},
                        raising=False)
    assert AS.handle_schedule_run({"force": True})["zorla"] is True


def test_serve_stdio_loop(monkeypatch):
    satirlar = ["{bozuk-json", '{"id": 1, "method": "app.version"}', "",
                '{"id": 2, "method": "app.version"}']

    class SahteStdin:
        def readline(self):
            return satirlar.pop(0) if satirlar else ""

    gonderilen = []
    monkeypatch.setattr(sys, "stdin", SahteStdin())
    monkeypatch.setattr("select.select",
                        lambda *a: (True, [], []))
    monkeypatch.setattr(AS, "_send", lambda o: gonderilen.append(o) or (_ for _ in ()).throw(KeyboardInterrupt()))
    monkeypatch.setattr(json_mod := __import__("json"), "loads",
                        json_loads_orijinal := json_mod.loads)

    def akilli_loads(s):
        if s == "{bozuk-json":
            raise json_mod.JSONDecodeError("hata", s, 0)
        return json_loads_orijinal(s)
    monkeypatch.setattr(json_mod, "loads", akilli_loads)
    monkeypatch.setattr(AS, "_ensure_qapp",
                        lambda: NS(processEvents=lambda: None))
    monkeypatch.setattr(AS, "_restore", lambda: 0, raising=False)

    import threading as th
    monkeypatch.setattr(th.Thread, "start", lambda self: None)

    try:
        AS.serve()                                                # 1317-1348
    except KeyboardInterrupt:
        pass
    assert len(gonderilen) == 1   # yalniz gecerli satir dispatch edilir