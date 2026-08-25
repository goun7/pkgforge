"""Coverage itmesi — ui/result_dialog.py guvenlik/distrobox/dosya kartlari ve JSON aktarimi."""
from __future__ import annotations

import os
from types import SimpleNamespace as NS

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from core.compatibility_checker import (
    CheckResult,
    CheckSeverity,
    CompatibilityReport,
)
from ui.result_dialog import ResultDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _meta(**kw):
    base = {"name": "demo", "version": "1.0", "arch": "amd64",
            "arch_mapped": "x86_64", "description": "Deneme paketi",
            "file_list": ["usr/bin/demo", "etc/demo.conf", "usr/share/doc/"],
            "already_installed": False, "installed_version": ""}
    base.update(kw)
    return NS(**base)


def _report(sev=CheckSeverity.PASS):
    return CompatibilityReport(checks=[
        CheckResult(name="ABI", severity=sev, message="mesaj",
                    details=["detay1", "detay2"]),
    ])


def _all_text(w):
    return " ".join(l.text() for l in w.findChildren(QLabel))


def _buttons(w):
    return [b.text() for b in w.findChildren(QPushButton)]


# --- kart insa dallari ----------------------------------------------------------

def test_security_card_with_sha_and_signature(app):
    sig = NS(has_signature=True, detail="imzalı")
    d = ResultDialog(_report(), metadata=_meta(), signature=sig,
                     sha256="ab" * 32)
    metin = _all_text(d)
    assert ("ab" * 16) in metin and "imzalı" in metin
    d.deleteLater()


def test_security_card_unsigned_color_branch(app):
    sig = NS(has_signature=False, detail="imzasız")
    d = ResultDialog(_report(), metadata=None, signature=sig)
    assert "imzasız" in _all_text(d)
    d.deleteLater()


def test_distrobox_card_on_error(app):
    d = ResultDialog(_report(CheckSeverity.ERROR), metadata=_meta(),
                     show_distrobox=True)
    metin = _all_text(d)
    assert any("distrobox" in m.lower() for m in metin.split())
    istekler = []
    d.distrobox_requested.connect(lambda: istekler.append(True))
    d._on_distrobox()
    assert istekler
    d.deleteLater()


def test_no_distrobox_card_when_not_error(app):
    d = ResultDialog(_report(CheckSeverity.WARNING), metadata=_meta(),
                     show_distrobox=True)
    # distrobox teklif etiketleri yok
    assert not [l for l in d.findChildren(QLabel)
                if "distrobox" in l.text().lower()]
    d.deleteLater()


def test_info_card_installed_field(app):
    d = ResultDialog(_report(), metadata=_meta(already_installed=True,
                                               installed_version="0.9"))
    assert "✓ 0.9" in _all_text(d)
    d.deleteLater()


def test_files_card_toggle_roundtrip(app):
    d = ResultDialog(_report(), metadata=_meta())
    d.show()  # isVisible() sozlesmesi icin widget ekranda olmali
    # dosya kartinin ac/kapa dugmesi ▶ ile baslar
    btns = [b for b in d.findChildren(QPushButton) if b.text().startswith("▶")]
    assert btns and len(btns) == 1
    btns[0].click()  # acilir -> onizleme gorunur, ok doner
    assert not btns[0].text().startswith("▶")
    btns[0].click()
    assert btns[0].text().startswith("▶")
    d.deleteLater()


def test_read_only_hides_install(app):
    from i18n import tr
    d = ResultDialog(_report(), metadata=_meta(), read_only=True)
    metinler = _buttons(d)
    kur_metni = tr("btn.install")
    herhangi_kur = tr("btn.install_anyway")
    assert kur_metni not in metinler and herhangi_kur not in metinler
    assert tr("btn.close") in metinler
    d.deleteLater()


def test_error_severity_offers_install_anyway(app):
    d = ResultDialog(_report(CheckSeverity.ERROR), metadata=_meta())
    assert any("yine de" in m.lower() or "anyway" in m.lower()
               for m in _buttons(d))
    d.deleteLater()


# --- JSON aktarimi --------------------------------------------------------------

def test_export_report_success(app, tmp_path, monkeypatch):
    hedef = tmp_path / "rapor.json"
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                        staticmethod(lambda *a, **k: (str(hedef), "")))
    cagrilar = []
    monkeypatch.setattr("core.report_export.save_report_json",
                        lambda path, report, **kw: cagrilar.append((path, kw)))
    bilgi = []
    monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox.information",
                        staticmethod(lambda *a, **k: bilgi.append(a)))
    meta = _meta()
    d = ResultDialog(_report(), metadata=meta, sha256="ff")
    d._on_export_report()
    assert cagrilar and cagrilar[0][0] == str(hedef)
    assert cagrilar[0][1]["metadata"] is meta
    assert bilgi
    d.deleteLater()


def test_export_report_cancelled_silent(app, tmp_path, monkeypatch):
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    cagrilar = []
    monkeypatch.setattr("core.report_export.save_report_json",
                        lambda *a, **k: cagrilar.append(a))
    d = ResultDialog(_report())
    d._on_export_report()
    assert cagrilar == []
    d.deleteLater()


def test_export_report_oserror_shows_critical(app, tmp_path, monkeypatch):
    def boom(*a, **kw):
        raise OSError("disk dolu")
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                        staticmethod(lambda *a, **k: ("/tmp/r.json", "")))
    monkeypatch.setattr("core.report_export.save_report_json", boom)
    kritik = []
    monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox.critical",
                        staticmethod(lambda *a, **k: kritik.append(a)))
    d = ResultDialog(_report())
    d._on_export_report()
    assert kritik and "disk dolu" in kritik[0][2]
    d.deleteLater()


def test_export_without_metadata_uses_default_name(app, tmp_path, monkeypatch):
    yakalanan = {}

    def _fake_dialog(*a, **k):
        yakalanan["t"] = k.get("parent", a[2] if len(a) > 2 else "")
        return "", ""
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                        staticmethod(_fake_dialog))
    d = ResultDialog(_report())
    d._on_export_report()
    assert "package" in yakalanan["t"]
    d.deleteLater()

# --- %100 itmesi: onay, detay ac-kapa ------------------------------------------

def test_approve_button_emits_and_accepts(app):
    d = ResultDialog(_report(CheckSeverity.PASS), metadata=_meta())
    d.show()
    from i18n import tr
    kur = next(b for b in d.findChildren(QPushButton)
               if b.text() == tr("btn.install"))
    onaylar = []
    d.install_approved.connect(lambda: onaylar.append(True))
    kabul = []
    d.accepted.connect(lambda: kabul.append(True))
    kur.click()
    assert onaylar and kabul
    d.deleteLater()


def test_details_toggle_roundtrip(app):
    d = ResultDialog(_report(), metadata=_meta())
    d.show()
    from i18n import tr
    beklenen = tr("result.details_btn", count=2)
    btn = next(b for b in d.findChildren(QPushButton)
               if beklenen.split("▶")[-1].strip()[:4] in b.text()
               or "detay" in b.text().lower())
    btn.click()   # acilir -> ▼
    assert btn.text().startswith("▼")
    btn.click()   # kapanir -> ▶
    assert btn.text().startswith("▶")
    d.deleteLater()
