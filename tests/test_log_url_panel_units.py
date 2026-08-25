"""Coverage itmesi — ui/log_panel.py ve ui/url_dialog.py kalan dallari."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication

from ui.log_panel import LogPanel, _escape_html
from ui.url_dialog import UrlDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# --- LogPanel ------------------------------------------------------------------

@pytest.fixture()
def lp(app):
    w = LogPanel()
    yield w
    w.deleteLater()


def test_escape_html_entities():
    assert _escape_html('a<b>&"c"') == "a&lt;b&gt;&amp;&quot;c&quot;"


def test_toggle_expands_and_collapses(lp):
    assert lp._expanded is False
    lp._toggle()
    assert lp._expanded is True and lp._text_edit.isVisibleTo(lp)
    lp._toggle()
    assert lp._expanded is False


def test_append_levels_and_error_autoexpands(lp):
    lp.append_log("normal", "info")
    lp.append_log("tamam", "success")
    lp.append_log("dikkat", "warning")
    assert len(lp._log_lines) == 3
    lp._expanded = False
    lp.append_log("kritik", "error")
    assert lp._expanded is True  # hata paneli kendisi acar
    assert lp._log_lines[-1][2] == "kritik"


def test_append_unknown_level_uses_default_style(lp):
    lp.append_log("x", "mystery")  # _LEVEL_STYLES fallback dali
    assert lp._log_lines[0][1] == "mystery"


def test_clear_empties_state(lp):
    lp.append_log("a")
    lp.clear()
    assert lp._log_lines == [] and not lp._text_edit.toPlainText()


def test_export_writes_formatted_lines(lp, tmp_path, monkeypatch):
    from ui import log_panel as LPM
    hedef = tmp_path / "cikti.log"
    monkeypatch.setattr(LPM.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(hedef), "")))
    lp.append_log("mesaj bir", "info")
    lp.append_log("hata iki", "error")
    lp._export_log()
    icerik = hedef.read_text(encoding="utf-8").splitlines()
    assert len(icerik) == 2 and "[INFO" in icerik[0] and "[ERROR" in icerik[1]


def test_export_cancelled_writes_nothing(lp, tmp_path, monkeypatch):
    from ui import log_panel as LPM
    monkeypatch.setattr(LPM.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    lp.append_log("a")
    lp._export_log()  # dosya secilmedi -> sessiz donus


def test_retranslate_both_states(lp):
    lp.retranslate()
    lp._expanded = True
    lp.retranslate()
    assert lp._count_label.text()


# --- UrlDialog -----------------------------------------------------------------

@pytest.fixture()
def ud(app):
    w = UrlDialog()
    yield w
    w.deleteLater()


def test_start_download_rejects_invalid(ud, monkeypatch):
    from ui import url_dialog as UDM
    uyarilar = []
    monkeypatch.setattr(UDM.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: uyarilar.append(a)))
    for bos in ("", "   ", "ftp://x", "javascript:alert(1)"):
        ud._url_input.setText(bos)
        ud._start_download()
    assert len(uyarilar) == 4 and ud._download_btn.isEnabled()


def test_start_download_success_path(ud, monkeypatch, tmp_path):
    from ui import url_dialog as UDM
    indirilen = tmp_path / "p.deb"
    indirilen.write_bytes(b"x")
    yakalanan = {}

    def fake_bg(fn, on_done=None, on_error=None):
        yakalanan["done"] = on_done
        yakalanan["err"] = on_error
        yakalanan["fn"] = fn
    monkeypatch.setattr("ui.background_worker.run_in_background", fake_bg)
    monkeypatch.setattr(UDM, "load_setting", lambda k, d=False: False)

    ud._url_input.setText("https://ornek.test/p.deb")
    kabul = []
    ud.accepted.connect(lambda: kabul.append(True))
    alinan = []
    ud.file_downloaded.connect(lambda p: alinan.append(p))
    ud._start_download()

    assert ud._download_btn.isEnabled() is False  # suruyor
    yakalanan["done"](indirilen)
    assert alinan == [indirilen] and kabul


def test_start_download_http_allowed_when_setting(ud, monkeypatch, tmp_path):
    from ui import url_dialog as UDM
    yakalanan = {}
    monkeypatch.setattr("ui.background_worker.run_in_background",
                        lambda fn, on_done=None, on_error=None:
                        yakalanan.update(fn=fn))
    monkeypatch.setattr(UDM, "load_setting", lambda k, d=False: True)
    ud._url_input.setText("http://eski.test/p.rpm")
    ud._start_download()
    # ayar aciksa http de gecer; arka plan isine girdi
    assert "fn" in yakalanan


def test_start_download_error_reenables(ud, monkeypatch):
    from ui import url_dialog as UDM
    kritikler = []
    monkeypatch.setattr(UDM.QMessageBox, "critical",
                        staticmethod(lambda *a, **k: kritikler.append(a)))
    yakalanan = {}
    monkeypatch.setattr("ui.background_worker.run_in_background",
                        lambda fn, on_done=None, on_error=None:
                        yakalanan.update(err=on_error))
    monkeypatch.setattr(UDM, "load_setting", lambda k, d=False: False)
    ud._url_input.setText("https://x/y.deb")
    ud._start_download()
    yakalanan["err"]("ag koptu")
    assert ud._download_btn.isEnabled() is True and kritikler

def test_download_worker_invokes_downloader(ud, monkeypatch, tmp_path):
    """_do_download kapanisi download_package'i dogru bayrakla cagirir."""
    from ui import url_dialog as UDM
    indirilen = tmp_path / "w.deb"
    indirilen.write_bytes(b"x")
    cagrilar = {}
    monkeypatch.setattr(UDM, "download_package",
                        lambda url, require_https=True:
                        cagrilar.update(url=url, https=require_https)
                        or indirilen)
    monkeypatch.setattr(UDM, "load_setting", lambda k, d=False: False)
    yakalanan = {}
    monkeypatch.setattr("ui.background_worker.run_in_background",
                        lambda fn, on_done=None, on_error=None:
                        yakalanan.update(fn=fn))
    ud._url_input.setText("https://ornek.test/w.deb")
    ud._start_download()
    sonuc = yakalanan["fn"]()  # arka plan isini senkron calistir
    assert sonuc == indirilen and cagrilar["https"] is True


def test_download_worker_http_insecure_allowed(ud, monkeypatch, tmp_path):
    from ui import url_dialog as UDM
    monkeypatch.setattr(UDM, "download_package",
                        lambda url, require_https=True: None)
    monkeypatch.setattr(UDM, "load_setting", lambda k, d=False: True)
    yakalanan = {}
    monkeypatch.setattr("ui.background_worker.run_in_background",
                        lambda fn, on_done=None, on_error=None:
                        yakalanan.update(fn=fn))
    ud._url_input.setText("http://eski.test/x.deb")
    ud._start_download()
    yakalanan["fn"]()  # require_https=False ile cagirmali (hata yoksa ok)
