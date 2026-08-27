"""Coverage itmesi — ui/drop_zone.py surukleme-birakma ve secim dallari."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication

from ui.drop_zone import DropZone


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def dz(app):
    w = DropZone()
    yield w
    w.deleteLater()


class _Ev:
    """dragEnter/drop olaylarinin kullandigi minimal yuzey."""

    def __init__(self, urls=None, has_urls=True):
        self._urls = urls or []
        self._has = has_urls
        self.accepted = False
        self.ignored = False

    def mimeData(self):
        if not self._has:
            return None
        return NS(hasUrls=lambda: bool(self._urls), urls=lambda: self._urls)

    def acceptProposedAction(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


def _url(path: str):
    return NS(toLocalFile=lambda: path)


def test_instantiation_builds_children(dz):
    assert dz.objectName() == "dropZone"
    assert dz._pick_btn is not None and dz._pick_btn.text() != ""


def _collect(dz):
    got = []
    dz.files_dropped.connect(lambda paths: got.append(list(paths)))
    return got


def test_drag_enter_none_event_returns(dz):
    dz.dragEnterEvent(None)  # cokmemeli


def test_drag_enter_without_urls_ignores(dz):
    ev = _Ev(urls=[], has_urls=True)
    dz.dragEnterEvent(ev)
    assert ev.ignored and not ev.accepted


def test_drag_enter_rejected_suffix_ignores(dz):
    ev = _Ev(urls=[_url("/tmp/notlar.txt")])
    dz.dragEnterEvent(ev)
    assert ev.ignored


def test_drag_enter_accepts_deb_and_marks_active(dz, tmp_path):
    f = tmp_path / "paket.DEB"  # buyuk harf de kabul
    f.write_bytes(b"x")
    ev = _Ev(urls=[_url(str(tmp_path / "diger.txt")), _url(str(f))])
    dz.dragEnterEvent(ev)
    assert ev.accepted and not ev.ignored
    assert dz.property("dragActive") is True
    # ikinci giris erken doner; etiket aktif metni tasir
    assert dz._main_label.text()


def test_drag_leave_resets(dz):
    dz.setProperty("dragActive", True)
    ev = NS(accept=lambda: None)
    dz.dragLeaveEvent(ev)
    assert dz.property("dragActive") is False
    dz.dragLeaveEvent(None)  # event None dalı


def test_drop_none_or_no_mime_ignored(dz, tmp_path):
    dz.dropEvent(None)
    ev = _Ev(has_urls=False)
    dz.dropEvent(ev)
    assert ev.ignored


def test_drop_valid_files_emitted(dz, tmp_path):
    a = tmp_path / "a.deb"; a.write_bytes(b"a")
    b = tmp_path / "b.rpm"; b.write_bytes(b"b")
    got = _collect(dz)
    ev = _Ev(urls=[_url(str(a)), _url(str(b)),
                   _url(str(tmp_path / "yok.deb")),
                   _url(str(tmp_path / "c.txt"))])
    dz.dropEvent(ev)
    assert ev.accepted and [Path(str(x)) for x in got[0]] == [a, b]


def test_drop_only_invalid_ignores(dz, tmp_path):
    got = _collect(dz)
    ev = _Ev(urls=[_url(str(tmp_path / "yok.deb")),
                   _url(str(tmp_path / "c.txt"))])
    dz.dropEvent(ev)
    assert ev.ignored and got == []


def test_pick_file_accepts_all_and_emits(dz, monkeypatch, tmp_path):
    good = tmp_path / "g.rpm"; good.write_bytes(b"g")
    txt = tmp_path / "h.txt"; txt.write_bytes(b"h")
    from ui import drop_zone as DZM
    monkeypatch.setattr(DZM.QFileDialog, "getOpenFileNames",
                        staticmethod(lambda *a, **k: ([str(good), str(txt)], "")))
    got = _collect(dz)
    dz._on_pick_file()
    assert [Path(str(x)) for x in got[0]] == [good, txt]


def test_drop_accepts_tarball_and_dir(dz, tmp_path):
    tar = tmp_path / "app.tar.gz"; tar.write_bytes(b"x")
    src = tmp_path / "kaynak"; src.mkdir()
    got = _collect(dz)
    ev = _Ev(urls=[_url(str(tar)), _url(str(src)), _url(str(tmp_path / "yok.tar.gz"))])
    dz.dropEvent(ev)
    assert ev.accepted and [Path(str(x)) for x in got[0]] == [tar, src]


def test_drag_enter_accepts_existing_tarball(dz, tmp_path):
    tar = tmp_path / "app.tar.gz"; tar.write_bytes(b"x")
    ev = _Ev(urls=[_url(str(tar))])
    dz.dragEnterEvent(ev)
    assert ev.accepted and not ev.ignored


def test_pick_file_empty_selection_silent(dz, monkeypatch):
    from ui import drop_zone as DZM
    monkeypatch.setattr(DZM.QFileDialog, "getOpenFileNames",
                        staticmethod(lambda *a, **k: ([], "")))
    got = _collect(dz)
    dz._on_pick_file()
    assert got == []


def test_set_processing_toggles_state(dz):
    dz.set_processing(True)
    assert dz.acceptDrops() is False and dz._pick_btn.isEnabled() is False
    assert dz._main_label.text()
    dz.set_processing(False)
    assert dz.acceptDrops() is True and dz._pick_btn.isEnabled() is True


def test_set_file_info_and_queue_and_retranslate(dz):
    dz.set_file_info("demo.deb", "deb")
    assert "📦" in dz._main_label.text() and "demo.deb" in dz._main_label.text()
    dz.set_queue_info(3)
    dz.retranslate()
    assert dz._sub_label.text()
