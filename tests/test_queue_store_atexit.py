"""QueueStore atexit kapanisi — thread sahipligi hatasi cabuk uretmemeli.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: sqlite GERCEKTEN kullanilir (ayni-thread kuralini taklit etmek imkansiz,
         cunku kuralin kendisi surukumuzun kaniti); dosyalar tmp_path'te, ag yok.

Tarihce (2026-10-16 guncellendi):
1) handlers_queue._get_queue_store() singleton'i ilk queue istegini isleyen
   is parcaciginda olusuyor; atexit ise Ana thread'de calisiyor. Baglanti
   kurucusu thread'e kilitli oldugu icin ham `.close()` ProgrammingError
   atiyordu; bu yuzden _close_queue_store sarmalayicisi gerekliydi.
2) AYNI sahiplik kurali YAZMALARI da kırıyordu: `upsert` worker thread'inde
   ProgrammingError atıyor, `_persist_item` hatayı yuttuğu için `queue.add`
   `{"added": 1}` dönüyor ama `queue.db` BOŞ kalıyordu (ölçüldü).
   QueueStore artik `check_same_thread=False` + ic kilit ile calisiyor;
   kalıcılık testleri: tests/test_queue_store_threading.py.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

import core.api.handlers_queue as HQ
from core.queue_store import QueueStore


def _threadde_kur(tmp_path: Path, ad: str) -> QueueStore:
    holder: dict[str, QueueStore] = {}

    def kur() -> None:
        holder["s"] = QueueStore(tmp_path / ad)

    t = threading.Thread(target=kur)
    t.start()
    t.join()
    return holder["s"]


def test_capraz_thread_close_artik_hata_vermez(tmp_path):
    """2026-10-16 sozlesme degisikligi: baglanti paylasilir, kapanis sessiz.

    Bu test eskiden ham `.close()`'un `ProgrammingError` firlattigini
    sabitliyordu (baglanti kurucusu thread'e kilitliydi). `QueueStore` artik
    `check_same_thread=False` + ic kilit ile calisiyor; ayni degisiklik
    kuyruk yazmalarini da worker thread'lerde kalici kildi
    (test_queue_store_threading.py).
    """
    store = _threadde_kur(tmp_path, "raw.db")
    store.close()                        # ana thread'de: artik yasal
    with pytest.raises(sqlite3.ProgrammingError):
        store._conn.execute("SELECT 1")  # kapanmis baglanti kullanilamaz


def test_sarmalayici_gercek_hatayi_yutar(tmp_path):
    """Sarmalayicinin yutma davranisi boslukta degil, gercek hatada test edilir."""
    class KapanirkenPatlayan:
        def close(self) -> None:
            raise sqlite3.ProgrammingError("baglanti bu thread'e ait degil")

    HQ._close_queue_store(KapanirkenPatlayan())   # sessiz olmali


def test_sarmalayici_gecerli_kapatmayi_gercekten_kapatir(tmp_path):
    """Kapanis sahipli thread'deyse asıl islev (baglantiyi birakmak) surmeli."""
    store = QueueStore(tmp_path / "own.db")
    HQ._close_queue_store(store)
    with pytest.raises(sqlite3.ProgrammingError):
        store._conn.execute("SELECT 1")   # kapatilmis baglanti kullanilamaz


def test_atexit_kaydi_sarmalayiciyi_kaydeder(monkeypatch, tmp_path):
    """Singleton kurilirken dogrudan .close degil, sarmalayici kaydedilmeli."""
    kayit: list[tuple] = []
    monkeypatch.setattr(HQ.atexit, "register",
                        lambda fn, *a: kayit.append((fn, a)))
    monkeypatch.setattr(HQ, "_queue_store", None)
    monkeypatch.setattr("core.queue_store.queue_db_path",
                        lambda: tmp_path / "reg.db")
    store = HQ._get_queue_store()
    assert store is not None
    assert len(kayit) == 1
    fn, args = kayit[0]
    assert fn is HQ._close_queue_store
    assert args == (store,)
    HQ._close_queue_store(store)          # temizlik: kapanmis halde birakma


def test_sarmalayici_hic_bir_istisna_yaymaz(tmp_path):
    """Kapanista istisna yaymak interpreter gürultusu; hic bir girdide olmamali."""
    class Kotu:
        def close(self):
            raise RuntimeError("beklenmedik")

    HQ._close_queue_store(Kotu())         # sessiz


def test_sentinel_kurulum_hatasi_yine_devam_ettirir(monkeypatch, tmp_path):
    """DB kurulumu patlarsa store False sentinel'i olur ve None doner."""
    monkeypatch.setattr(HQ, "_queue_store", None)

    def patla(*a, **k):
        raise OSError("disk dolu")

    monkeypatch.setattr("core.queue_store.QueueStore", patla)
    assert HQ._get_queue_store() is None
    assert HQ._queue_store is False

