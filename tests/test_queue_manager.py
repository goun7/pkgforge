"""Coverage itmesi — core/queue_manager.py (coklu paket kuyrugu)."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.queue_manager import QueueItem, QueueItemStatus, QueueManager


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtCore import QCoreApplication

    return QCoreApplication.instance() or QCoreApplication([])


def _mk(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_bytes(b"x")
    return p


def test_queue_item_properties(tmp_path):
    item = QueueItem(file_path=tmp_path / "hello.deb")
    assert item.name == "hello.deb"
    assert item.pkg_type == "deb"
    rpm = QueueItem(file_path=tmp_path / "x.rpm")
    assert rpm.pkg_type == "rpm"


def test_add_files_filters_and_dedupes(qapp, tmp_path):
    qm = QueueManager()
    deb = _mk(tmp_path, "a.deb")
    rpm = _mk(tmp_path, "b.rpm")
    txt = _mk(tmp_path, "c.txt")
    qm.add_files([deb, rpm, txt, deb])  # txt gecersiz, deb tekrar
    assert qm.total == 2
    assert qm.pending_count == 2


def test_remove_only_pending(qapp, tmp_path):
    qm = QueueManager()
    deb = _mk(tmp_path, "a.deb")
    qm.add_files([deb])
    qm.mark_started(0)  # artik PROCESSING
    qm.remove_item(0)
    assert qm.total == 1  # silinmedi


def test_clear_keeps_processing(qapp, tmp_path):
    qm = QueueManager()
    a = _mk(tmp_path, "a.deb")
    b = _mk(tmp_path, "b.deb")
    qm.add_files([a, b])
    qm.mark_started(0)
    qm.clear()
    assert qm.total == 1  # sadece PROCESSING kalir


def test_get_next_and_lifecycle(qapp, tmp_path):
    qm = QueueManager()
    a = _mk(tmp_path, "a.deb")
    b = _mk(tmp_path, "b.deb")
    qm.add_files([a, b])
    nxt = qm.get_next()
    assert nxt is not None
    idx = nxt[0]
    assert idx == 0
    qm.mark_started(idx)
    assert qm.is_processing
    qm.mark_finished(idx, True, "ok")
    assert qm.items[0].status == QueueItemStatus.DONE
    # siradaki pending
    assert qm.get_next()[0] == 1


def test_all_finished_resets(qapp, tmp_path):
    qm = QueueManager()
    a = _mk(tmp_path, "a.deb")
    qm.add_files([a])
    qm.mark_started(0)
    qm.mark_finished(0, False, "hata")
    assert qm.items[0].status == QueueItemStatus.ERROR
    assert not qm.is_processing
    assert qm.current_index == -1


def test_get_summary(qapp, tmp_path):
    qm = QueueManager()
    a = _mk(tmp_path, "a.deb")
    b = _mk(tmp_path, "b.deb")
    qm.add_files([a, b])
    qm.mark_started(0)
    qm.mark_finished(0, True)
    s = qm.get_summary()
    assert s.get("done") == 1
    assert s.get("pending") == 1
