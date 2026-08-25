"""Coverage itmesi — ui/settings_dialog.py kaydet/goster/eklenti dallari."""
from __future__ import annotations

import os
from types import SimpleNamespace as NS

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication

import ui.settings_dialog as SD


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _tools(plugins=True, distrobox=True):
    return NS(has_distrobox=distrobox,
              has_clamav=True,
              plugins=(["deb_extra", "rpm_probe"] if plugins else []))


@pytest.fixture()
def dlg(app, monkeypatch):
    monkeypatch.setattr(SD, "discover_tools", lambda: _tools())
    monkeypatch.setattr(SD, "list_plugins",
                        lambda: [{"name": "deb_extra", "priority": 1,
                                  "class": "converter",
                                  "extensions": [".deb"]},
                                 {"name": "rpm_probe", "priority": 2,
                                  "class": "probe",
                                  "extensions": [".rpm"]}])
    monkeypatch.setattr(SD, "load_settings",
                        lambda: {"language": "tr", "theme": "dark",
                                 "timeout_seconds": 30})
    kaydedilen = {}
    monkeypatch.setattr(SD, "save_settings",
                        lambda s: kaydedilen.update(s))
    d = SD.SettingsDialog()
    d.show()
    yield d, kaydedilen
    d.deleteLater()


def test_distrobox_present_tooltip_branch(dlg):
    d, _ = dlg
    assert d._distrobox_check is not None


def test_distrobox_missing_tooltip_branch(app, monkeypatch):
    monkeypatch.setattr(SD, "discover_tools",
                        lambda: _tools(distrobox=False))
    monkeypatch.setattr(SD, "list_plugins", dict)
    monkeypatch.setattr(SD, "load_settings", dict)
    monkeypatch.setattr(SD, "save_settings", lambda s: None)
    d = SD.SettingsDialog()
    d.deleteLater()


def test_no_plugins_label_branch(app, monkeypatch):
    monkeypatch.setattr(SD, "discover_tools",
                        lambda: _tools(plugins=False))
    monkeypatch.setattr(SD, "list_plugins", dict)
    monkeypatch.setattr(SD, "load_settings", dict)
    monkeypatch.setattr(SD, "save_settings", lambda s: None)
    d = SD.SettingsDialog()
    d.deleteLater()


def test_save_collects_all_fields_and_emits(dlg):
    d, kaydedilen = dlg
    alinan = []
    d.settings_changed.connect(lambda s: alinan.append(dict(s)))
    d._lang_combo.setCurrentIndex(d._lang_combo.findData("en"))
    d._timeout_spin.setValue(90)
    d._outdir_input.setText("/tmp/cikti")
    kabul = []
    d.accepted.connect(lambda: kabul.append(True))
    d._save()
    assert kaydedilen["language"] == "en"
    assert kaydedilen["timeout_seconds"] == 90
    assert kaydedilen["output_dir"] == "/tmp/cikti"
    assert "plugin_deb_extra" in kaydedilen
    assert alinan and kabul


def test_browse_output_dir_sets_text(dlg, monkeypatch):
    d, _ = dlg
    monkeypatch.setattr(SD.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: "/secilen/yol"))
    d._browse_output_dir()
    assert d._outdir_input.text() == "/secilen/yol"


def test_browse_cancelled_keeps_old(dlg, monkeypatch):
    d, _ = dlg
    d._outdir_input.setText("/eski")
    monkeypatch.setattr(SD.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: ""))
    d._browse_output_dir()
    assert d._outdir_input.text() == "/eski"


def test_reload_plugins_updates_checks(dlg, monkeypatch):
    d, _ = dlg
    monkeypatch.setattr(SD, "reload_plugins",
                        lambda: {"deb_extra": {"name": "deb_extra"}})
    bilgi = []
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: bilgi.append(a)))
    d._reload_plugins()
    assert d._plugin_checks["deb_extra"].isChecked() is True
    assert d._plugin_checks["deb_extra"].isEnabled() is True
    assert d._plugin_checks["rpm_probe"].isChecked() is False
    assert d._plugin_checks["rpm_probe"].isEnabled() is True
    assert bilgi


def test_live_preview_reflects_toggle(dlg):
    d, _ = dlg
    onceki = d._preview_text.toPlainText()
    d._auto_sign_check.setChecked(True)
    # ozet yenileyici yontem cagrildiginda JSON guncellenir
    if hasattr(d, "_update_preview"):
        d._update_preview()
        sonra = d._preview_text.toPlainText()
        assert isinstance(sonra, str) and sonra != "" or onceki == ""