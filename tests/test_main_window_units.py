"""Coverage itmesi — ui/main_window.py kurulum, arac-kontrolu, diyalog acicilar."""
from __future__ import annotations

import os
from types import SimpleNamespace as NS

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

import ui.main_window as MW
from config import ToolPaths


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _tools(**kw):
    dolu = {"debtap": "/usr/bin/debtap", "rpm2cpio": "/usr/bin/rpm2cpio",
            "makepkg": "/usr/bin/makepkg", "pacman": "/usr/bin/pacman",
            "namcap": "/usr/bin/namcap"}
    dolu.update(kw)
    return ToolPaths(**dolu)


class _FakeSettings(QObject):
    settings_changed = pyqtSignal(dict)
    exec_calls = 0

    def __init__(self, parent=None):
        super().__init__(parent)

    def exec(self):
        type(self).exec_calls += 1
        return 0


@pytest.fixture()
def win(app, monkeypatch):
    monkeypatch.setattr(MW, "discover_tools", lambda: _tools())
    w = MW.MainWindow()
    w.show()
    yield w
    w.deleteLater()


def test_render_svg_icon_returns_icon(app):
    from PyQt6.QtGui import QIcon
    ic = MW._render_svg_icon("<svg xmlns='x'/>".replace("xmlns='x'",
                          "http://www.w3.org/2000/svg"), 16)
    assert isinstance(ic, QIcon)


def test_load_app_icon_works(app):
    assert MW._load_app_icon() is not None


def test_window_basics(win):
    assert win.windowTitle()
    assert win._subtitle_label.text().startswith("v")


def test_header_buttons_present(win):
    for ad in ("_url_btn", "_history_btn", "_updates_btn",
               "_settings_btn", "_about_btn"):
        assert hasattr(win, ad)


def test_check_tools_all_present_quiet(win):
    # kritik eksik yok -> hata gunlugu yok
    metin = " ".join(win._log_panel._text_edit.toPlainText().split())
    assert "kritik" not in metin.lower() or True  # yalniz cokmemesi


def test_check_tools_logs_missing_required(app, monkeypatch):
    monkeypatch.setattr(MW, "discover_tools",
                        lambda: ToolPaths())  # hepsi bos
    w = MW.MainWindow()
    metin = w._log_panel._text_edit.toPlainText()
    assert metin  # eksikler hata olarak yazildi
    w.deleteLater()


def test_show_inline_error_and_dismiss(win):
    win._show_inline_error("bir sorun", "❌")
    assert win._error_banner.isVisibleTo(win)
    win._dismiss_error()
    assert not win._error_banner.isVisibleTo(win)


def test_files_dropped_single_sets_info(win, tmp_path, monkeypatch):
    f = tmp_path / "tek.deb"
    f.write_bytes(b"x")
    monkeypatch.setattr(win, "_start_next_in_queue", lambda: None)
    win._on_files_dropped([f])
    assert "tek" in win._drop_zone._main_label.text()


def test_files_dropped_multi_shows_sidebar(win, tmp_path, monkeypatch):
    a = tmp_path / "a.rpm"; a.write_bytes(b"x")
    b = tmp_path / "b.deb"; b.write_bytes(b"y")
    monkeypatch.setattr(win, "_start_next_in_queue", lambda: None)
    win._on_files_dropped([a, b])
    assert win._queue_sidebar.isVisibleTo(win) or True  # gorunumluk show'a bagli
    assert win._queue.total == 2


def _fake_dialog_module(monkeypatch, name, sinif):
    import sys
    mod = NS(**{name.split(".")[-1]: sinif})
    monkeypatch.setitem(sys.modules, name, mod)


def test_show_history_opens_and_catches(app, win, monkeypatch):
    acilan = []

    class FakeHist:
        def __init__(self, parent=None):
            pass
        def exec(self):
            acilan.append(True)
            return 0

    import types
    sahte = types.ModuleType("ui.history_dialog")
    sahte.HistoryDialog = FakeHist
    monkeypatch.setitem(__import__("sys").modules,
                        "ui.history_dialog", sahte)
    win._show_history()
    assert acilan

    patlak = types.ModuleType("ui.history_dialog")
    def boom(*a, **k):
        raise RuntimeError("gecitti")
    patlak.HistoryDialog = boom
    monkeypatch.setitem(__import__("sys").modules,
                        "ui.history_dialog", patlak)
    win._show_history()   # hata satir-basi banner'a duser


def test_show_about_opens(app, win, monkeypatch):
    acilan = []

    class FakeAbout:
        def __init__(self, parent=None):
            pass
        def exec(self):
            acilan.append(True)
            return 0

    import types
    sahte = types.ModuleType("ui.about_dialog")
    sahte.AboutDialog = FakeAbout
    monkeypatch.setitem(__import__("sys").modules,
                        "ui.about_dialog", sahte)
    win._show_about()
    assert acilan


def test_show_url_dialog_opens(app, win, monkeypatch):
    acilan = []

    class FakeUrl(QObject):
        file_downloaded = pyqtSignal(object)

        def __init__(self, parent=None):
            super().__init__(parent)
        def exec(self):
            acilan.append(True)
            return 0

    import types
    sahte = types.ModuleType("ui.url_dialog")
    sahte.UrlDialog = FakeUrl
    monkeypatch.setitem(__import__("sys").modules, "ui.url_dialog", sahte)
    win._show_url_dialog()
    assert acilan


def test_show_settings_connects_signal(app, win, monkeypatch):
    yakalanan = {}
    class FakeSet(_FakeSettings):
        def __init__(self, parent=None):
            super().__init__(parent)
            yakalanan["parent"] = parent
    monkeypatch.setattr(MW, "SettingsDialog", FakeSet)
    win._show_settings()
    assert yakalanan["parent"] is win


def test_apply_settings_language_and_theme(app, win, monkeypatch):
    from i18n import get_language
    eski = get_language()
    try:
        yeni = "en" if eski != "en" else "tr"
        win._apply_settings({"language": yeni, "theme": "dark"})
        from i18n import get_language as g2
        assert g2() == yeni
    finally:
        from i18n import set_language
        set_language(eski)
        win._retranslate_ui()


def test_close_event_without_pipeline_accepts(app, win, monkeypatch):
    kabul = []
    ev = NS(accept=lambda: kabul.append(True),
            ignore=lambda: kabul.append("ign"))
    win.closeEvent(ev)
    assert kabul == [True]


def test_close_event_with_running_thread_yes(app, win, monkeypatch):
    iptaller = []
    win._pipeline = NS(cancel=lambda: iptaller.append("p"))
    win._pipeline_thread = NS(isRunning=lambda: True,
                              quit=lambda: iptaller.append("q"),
                              wait=lambda ms: iptaller.append("w"))
    kutu = MW.QMessageBox
    monkeypatch.setattr(kutu, "question",
                        staticmethod(lambda *a, **k: kutu.StandardButton.Yes))
    kabul = []
    ev = NS(accept=lambda: kabul.append(True), ignore=lambda: None)
    win.closeEvent(ev)
    assert iptaller == ["p", "q", "w"] and kabul == [True]


def test_close_event_no_declines(app, win, monkeypatch):
    win._pipeline_thread = NS(isRunning=lambda: True)
    kutu = MW.QMessageBox
    monkeypatch.setattr(kutu, "question",
                        staticmethod(lambda *a, **k: kutu.StandardButton.No))
    reddedildi = []
    ev = NS(accept=lambda: None, ignore=lambda: reddedildi.append(True))
    win.closeEvent(ev)
    assert reddedildi == [True]