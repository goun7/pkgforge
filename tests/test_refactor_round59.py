"""Tur-59 — kalite iyileştirmeleri: QProcess fabrika enjeksiyonu."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

TOOLS = NS(distrobox="/usr/bin/distrobox", rpm2cpio="/usr/bin/rpm2cpio",
           bsdtar="/usr/bin/bsdtar", makepkg="/usr/bin/makepkg")


def _sahte_surec_factory(kayit):
    """Enjekte edilen fabrika — ürettiği her süreci kaydeder."""

    def uret(parent=None):
        surec = NS(parent=parent)
        kayit.append(surec)
        return surec

    return uret


def test_deb_converter_injects_factory():
    from core.deb_converter import DebConverter

    cagri = []
    obj = DebConverter(TOOLS, None, process_factory=_sahte_surec_factory(cagri))
    p = obj._make_process(obj)
    assert p in cagri                                                  # truthy


def test_rpm_converter_injects_factory():
    from core.rpm_converter import RpmConverter

    cagri = []
    obj = RpmConverter(TOOLS, None, process_factory=_sahte_surec_factory(cagri))
    p = obj._make_process(obj)
    assert p in cagri and p.parent is obj                              # truthy


def test_installer_injects_factory():
    from core.installer import Installer

    cagri = []
    obj = Installer(TOOLS, None, process_factory=_sahte_surec_factory(cagri))
    assert obj._make_process(obj) in cagri                             # truthy


def test_native_deb_converter_injects_factory():
    from core.native_deb_converter import NativeDebConverter

    cagri = []
    obj = NativeDebConverter(TOOLS, None,
                             process_factory=_sahte_surec_factory(cagri))
    assert obj._make_process(obj) in cagri                             # truthy


def test_distrobox_fallback_injects_factory():
    from core.distrobox_fallback import DistroboxFallback

    cagri = []
    obj = DistroboxFallback(TOOLS, None,
                            process_factory=_sahte_surec_factory(cagri))
    assert obj._make_process(obj) in cagri                             # truthy


@pytest.mark.parametrize("modul_adi,sinif_adi", [
    ("core.deb_converter", "DebConverter"),
    ("core.rpm_converter", "RpmConverter"),
    ("core.installer", "Installer"),
    ("core.native_deb_converter", "NativeDebConverter"),
    ("core.distrobox_fallback", "DistroboxFallback"),
])
def test_default_process_returns_qprocess(modul_adi, sinif_adi):
    """Fabrika verilmezse varsayılan dal gerçek QProcess üretir."""
    import importlib

    from PyQt6.QtCore import QProcess

    modul = importlib.import_module(modul_adi)
    sinif = getattr(modul, sinif_adi)
    obj = sinif(TOOLS, None)
    qproc = obj._make_process(None)
    assert isinstance(qproc, QProcess)
