"""QueueStore is thread-safe where it matters: the sidecar persists from workers.

Olcuilen hata (2026-10-16): `sqlite3.connect()` `check_same_thread=False`
olmadan kuruluyordu; `_persist_item()` ise her hatayı yutuyordu
(`except Exception: pass`). Sonucunda toplu kuyruk yan-izeleklerinde HIC
kalici degildi — yanıt `{"added": 1}` dönüyor, `queue.db` bos kaliyordu:

    worker hatasi: ['ProgrammingError: SQLite objects created in a thread can
                    only be used in that same thread...']
    satir sayisi: 0

Bu, UI'nin "kuyruk devri" akisini da sessizce bozuyordu (ikinci "Birlikte ac"
örneğinin dosyaları yalnızca bellekte yaşıyordu).
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, ".")

from core.queue_store import QueueStore


def _item(i: int, path: Path) -> dict[str, object]:
    return {
        "id": f"q{i}",
        "path": str(path),
        "name": path.name,
        "status": "pending",
        "priority": 0,
        "message": "",
    }


def test_worker_thread_upsert_kayit_dusurur(tmp_path):
    db = tmp_path / "queue.db"
    src = tmp_path / "a.deb"
    src.write_bytes(b"x")
    store = QueueStore(db)  # ana thread'de olusturuldu

    hata: list[str] = []

    def worker() -> None:
        try:
            store.upsert(_item(1, src))
        except BaseException as exc:  # noqa: BLE001
            hata.append(f"{type(exc).__name__}: {exc}")

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=10)

    assert hata == [], hata
    got = store.load_restorable()
    assert [g["id"] for g in got] == ["q1"]


def test_birkac_thread_ayni_anda_yazabilir(tmp_path):
    db = tmp_path / "queue.db"
    store = QueueStore(db)
    kaynaklar = []
    for i in range(8):
        p = tmp_path / f"p{i}.deb"
        p.write_bytes(b"x")
        kaynaklar.append(p)

    hatalar: list[str] = []

    def yaz(i: int) -> None:
        try:
            store.upsert(_item(i, kaynaklar[i]))
        except BaseException as exc:  # noqa: BLE001
            hatalar.append(f"{type(exc).__name__}: {exc}")

    threadler = [threading.Thread(target=yaz, args=(i,)) for i in range(8)]
    for t in threadler:
        t.start()
    for t in threadler:
        t.join(timeout=15)

    assert hatalar == [], hatalar
    assert len(store.load_restorable()) == 8


def test_worker_thread_remove_clear_calisir(tmp_path):
    db = tmp_path / "queue.db"
    src = tmp_path / "a.deb"
    src.write_bytes(b"x")
    store = QueueStore(db)
    store.upsert(_item(1, src))
    sonuc: list[str] = []

    def worker() -> None:
        try:
            store.remove("q1")
            store.upsert(_item(2, src))
            store.clear()
        except BaseException as exc:  # noqa: BLE001
            sonuc.append(f"{type(exc).__name__}: {exc}")

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=10)

    assert sonuc == [], sonuc
    assert store.load_restorable() == []
