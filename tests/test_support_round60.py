"""Tur-60 — destek katmani: FUNDING.yml, bagis butonu, issue sablonlari."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

KOK = Path(__file__).resolve().parent.parent

# QApplication referansi modul duzeyinde tutulur; aksi halde test icinde
# olusturulan uygulama GC ile dusur ve QWidget "once QApplication" diyerek
# sureci abort eder (qFatal).
_QAPP = None


def _get_app():
    global _QAPP
    from PyQt6.QtWidgets import QApplication

    if _QAPP is None:
        _QAPP = QApplication.instance() or QApplication([])
    return _QAPP


def test_donate_url_constants():
    from config import DONATE_URL, REPO_URL

    assert DONATE_URL.startswith("https://")
    assert REPO_URL.startswith("https://github.com/")


def test_funding_yml_valid():
    import yaml

    data = yaml.safe_load((KOK / ".github" / "FUNDING.yml").read_text())
    assert data["github"] == ["goun7"]
    assert any("polar.sh" in u for u in data["custom"])


def test_issue_templates_exist():
    sablonlar = KOK / ".github" / "ISSUE_TEMPLATE"
    assert (sablonlar / "bug_report.md").is_file()
    assert (sablonlar / "feature_request.md").is_file()
    assert (sablonlar / "config.yml").is_file()


def test_about_support_button_opens_donate(monkeypatch):
    _get_app()
    import ui.about_dialog as AD

    yakalanan = []
    monkeypatch.setattr(
        AD.QDesktopServices, "openUrl",
        lambda url: yakalanan.append(url.toString()) or True,
    )
    dlg = AD.AboutDialog()
    assert dlg._open_support() is True
    assert yakalanan == [AD.DONATE_URL]


def test_about_support_i18n_keys():
    from i18n.lang_en import STRINGS as EN
    from i18n.lang_tr import STRINGS as TR

    assert "about.support" in TR
    assert "about.support" in EN
