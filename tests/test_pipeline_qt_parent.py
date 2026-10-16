"""Qt nesne-affinitesi kilidi: pipeline worker thread'de `self`i parent yapmaz.

Kanıt (gerçek masaüstü çalıştırması, 2026-10-16):
    pkgforge --file /tmp/pf_proof_home/gelip.deb
    ...
    QObject: Cannot create children for a parent that is in a different thread.
    (Parent is ConversionPipeline(0x55992ed1c2d0), parent's thread is QThread(...),
     current thread is QThread(...))

Sidecar pipeline'i main thread'de kuruyor, işi worker thread'de çalıştırıyor.
Qt parent'i sessizce yok saydığı için nesne omru garantisi de kayboluyordu;
_qt_parent() ayni thread disinda None doner ve omru Python alanlari tasir.
"""
from __future__ import annotations

import ast
import os
import threading
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtCore")

from PyQt6.QtWidgets import QApplication

from core.pipeline import _HAS_PYQT6, ConversionPipeline

PIPELINE_PY = Path(__file__).resolve().parent.parent / "core" / "pipeline.py"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.skipif(not _HAS_PYQT6, reason="PyQt6 yok")
def test_ayni_threadde_parent_pipeline_kendisi(app):
    pipe = ConversionPipeline()
    assert pipe._qt_parent() is pipe


@pytest.mark.skipif(not _HAS_PYQT6, reason="PyQt6 yok")
def test_worker_threadde_parent_none(app):
    """Sidecar'ın gercek calisma sekli: pipeline main thread'de, is worker'da."""
    pipe = ConversionPipeline()
    sonuc: list[object] = []

    def kosan():
        sonuc.append(pipe._qt_parent())

    t = threading.Thread(target=kosan)
    t.start()
    t.join(timeout=5)
    assert sonuc == [None]


@pytest.mark.skipif(not _HAS_PYQT6, reason="PyQt6 yok")
def test_parent_none_olan_qprocess_yine_ayni_threadde(app):
    """Parent'siz QObject, olustugu thread'e aittir; Qt uyarisi uretilmez."""
    from config import discover_tools
    from core.native_deb_converter import NativeDebConverter

    pipe = ConversionPipeline()
    hata: list[object] = []

    def kosan():
        try:
            conv = NativeDebConverter(discover_tools(), pipe._qt_parent())
            hata.append(conv.thread() is not pipe.thread())
        except BaseException as exc:  # noqa: BLE001
            hata.append(exc)

    t = threading.Thread(target=kosan)
    t.start()
    t.join(timeout=10)
    assert hata == [True]


def test_pipeline_qt_parent_kullanimi_ratcheti():
    """Kalici kilic: `Converter(self._tools, self)` deseni geri gelmesin."""
    agac = ast.parse(PIPELINE_PY.read_text(encoding="utf-8"))
    kotu: list[str] = []
    for dugum in ast.walk(agac):
        if not isinstance(dugum, ast.Call):
            continue
        ad = getattr(dugum.func, "id", "") or getattr(dugum.func, "attr", "")
        if not (ad.endswith("Converter") or ad == "Installer"):
            continue
        for arg in dugum.args[1:]:
            if isinstance(arg, ast.Name) and arg.id == "self":
                kotu.append(f"{ad}(...) satir {dugum.lineno}")
    assert kotu == [], kotu
