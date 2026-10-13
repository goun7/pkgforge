"""QueueStore atexit kapanisi — thread sahipligi hatasi cabuk uretmemeli.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: sqlite GERCEKTEN kullanilir (ayni-thread kuralini taklit etmek imkansiz,
         cunku kuralin kendisi surukumuzun kaniti); dosyalar tmp_path'te, ag yok.

Neden var: handlers_queue._get_queue_store() singleton'i ilk queue istegini
isleyen is parcaciginda olusuyor; atexit ise Ana thread'de calisiyor.
sqlite3 bir baglantiyi kurucusu disindaki thread'de kullanimi reddettigi icin
`atexit.register(_queue_store.close)` her sidecar kapanisinda
ProgrammingError izlegi basiyordu (alt-ajan iki kez uretti) ve yorumun iddia
ettigi temizlik (WAL + dosya tutamaci) HIC yapilmiyordu.
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


def test_capraz_thread_close_gercekten_hata_verir(tmp_path):
    """Kök nedeni sabitle: ham .close() ProgrammingError firlatiyor olmali.

    Bu test olmaksizin duzeltme 'olmayan bir hatayi yutuyor' olurdu; sqlite
    surumu/kurulumu degisirse test buradan kirilir ve uyari verir.
    """
    store = _threadde_kur(tmp_path, "raw.db")
    with pytest.raises(sqlite3.ProgrammingError):
        store.close()


def test_sarmalayici_hatayi_yutar_ve_caburmaz(tmp_path):
    store = _threadde_kur(tmp_path, "wrapped.db")
    HQ._close_queue_store(store)          # sessiz olmali


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

