"""Faz 5 (F5.12) — batch kuyruk sqlite kalıcılığı ve yeniden başlatma."""
from __future__ import annotations

from pathlib import Path

import pytest

import core.api_server as A
import core.queue_store as QS


@pytest.fixture
def isolated_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(
        QS, "queue_db_path", lambda profile=None: tmp_path / "queue.db")
    monkeypatch.setattr(A, "_queue_store", None)
    A.handlers_queue._queue_items.clear()
    monkeypatch.setattr(A, "_queue_seq", 0)
    yield tmp_path
    A.handlers_queue._queue_items.clear()
    store = A.handlers_queue._queue_store
    if store:
        try:
            store.close()
        except Exception:  # noqa: BLE001, S110 - teardown best-effort
            pass
    A.handlers_queue._queue_store = None
    A.handlers_queue._queue_seq = 0


def _mkpkg(root: Path, name: str) -> Path:
    p = root / name
    p.write_bytes(b"fake")
    return p


# --- QueueStore birim testleri -------------------------------------------

def test_store_upsert_and_load_coerces_running_to_pending(tmp_path):
    deb = _mkpkg(tmp_path, "a.deb")
    store = QS.QueueStore(tmp_path / "q.db")
    store.upsert({"id": "q1", "path": str(deb), "name": "a.deb",
                  "status": "running", "priority": 3, "message": "x"})
    store.close()

    store2 = QS.QueueStore(tmp_path / "q.db")
    items = store2.load_restorable()
    store2.close()
    assert len(items) == 1
    assert items[0]["status"] == "pending"  # running -> pending
    assert items[0]["priority"] == 3
    assert items[0]["message"] == ""  # message not resurrected


def test_store_skips_terminal_and_missing_files(tmp_path):
    deb = _mkpkg(tmp_path, "ok.deb")
    store = QS.QueueStore(tmp_path / "q.db")
    store.upsert({"id": "q1", "path": str(deb), "name": "ok.deb",
                  "status": "done", "priority": 0, "message": ""})
    store.upsert({"id": "q2", "path": str(tmp_path / "gone.deb"),
                  "name": "gone.deb", "status": "pending", "priority": 0,
                  "message": ""})
    store.close()

    store2 = QS.QueueStore(tmp_path / "q.db")
    assert store2.load_restorable() == []  # done skipped, missing skipped
    store2.close()


def test_store_remove_and_clear(tmp_path):
    deb = _mkpkg(tmp_path, "a.deb")
    store = QS.QueueStore(tmp_path / "q.db")
    store.upsert({"id": "q1", "path": str(deb), "name": "a.deb",
                  "status": "pending", "priority": 0, "message": ""})
    store.remove("q1")
    assert store.load_restorable() == []
    store.upsert({"id": "q2", "path": str(deb), "name": "a.deb",
                  "status": "pending", "priority": 0, "message": ""})
    store.clear()
    assert store.load_restorable() == []
    store.close()


# --- api_server entegrasyon (yeniden baslatma simulasyonu) ---------------

def test_add_persists_and_restart_restores(isolated_queue):
    deb = _mkpkg(isolated_queue, "hello.deb")
    assert A.handle_queue_add({"paths": [str(deb)]}) == {"added": 1}
    assert len(A.handlers_queue._queue_items) == 1

    # Simulate a restart: in-memory state is gone, db remains.
    A.handlers_queue._queue_items.clear()
    A.handlers_queue._queue_seq = 0
    restored = A.restore_queue()
    assert restored == 1
    items = A.handle_queue_list({})
    assert len(items) == 1
    assert items[0]["path"] == str(deb)
    assert items[0]["status"] == "pending"
    assert A.handlers_queue._queue_seq >= 1  # sequence advanced past restored id


def test_done_item_not_restored(isolated_queue):
    deb = _mkpkg(isolated_queue, "hello.deb")
    A.handle_queue_add({"paths": [str(deb)]})
    item_id = next(iter(A.handlers_queue._queue_items))
    A.handlers_queue._set_item(item_id, status="done", message="bitti")

    A.handlers_queue._queue_items.clear()
    assert A.restore_queue() == 0


def test_remove_persists(isolated_queue):
    deb = _mkpkg(isolated_queue, "hello.deb")
    A.handle_queue_add({"paths": [str(deb)]})
    item_id = next(iter(A.handlers_queue._queue_items))
    A.handle_queue_remove({"id": item_id})

    A.handlers_queue._queue_items.clear()
    assert A.restore_queue() == 0


def test_clear_persists(isolated_queue):
    deb = _mkpkg(isolated_queue, "hello.deb")
    A.handle_queue_add({"paths": [str(deb)]})
    A.handle_queue_clear({})

    A.handlers_queue._queue_items.clear()
    assert A.restore_queue() == 0


def test_priority_change_persists(isolated_queue):
    deb = _mkpkg(isolated_queue, "hello.deb")
    A.handle_queue_add({"paths": [str(deb)]})
    item_id = next(iter(A.handlers_queue._queue_items))
    A.handle_queue_priority({"id": item_id, "priority": 9})

    A.handlers_queue._queue_items.clear()
    A.restore_queue()
    items = A.handle_queue_list({})
    assert items[0]["priority"] == 9
