"""Coverage itmesi — ui/history_dialog.py filtre/dosya-islemleri/yasam-dongusu."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication

import ui.history_dialog as HD


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _rec(**kw):
    base = {"id": 1, "timestamp": "2025-01-01 10:00", "package_name": "demo",
            "package_type": "deb", "status": "installed",
            "original_file": "/x/demo.deb", "source_url": "",
            "backup_pkg": None}
    base.update(kw)
    return NS(**base)


class FakeDB:
    def __init__(self, records=None, for_package=None):
        self._records = records or []
        self._for_package = for_package or []
        self.cleared = False
        self.added = []

    def get_history(self, limit=100):
        return list(self._records)

    def get_records_for_package(self, name):
        return list(self._for_package)

    def clear_history(self):
        self.cleared = True

    def add_record(self, **kw):
        self.added.append(kw)


@pytest.fixture()
def dlg(app, monkeypatch, tmp_path):
    db = FakeDB(records=[
        _rec(),
        _rec(id=2, package_name="gtk3", package_type="rpm",
             original_file="/y/gtk3.rpm", status="converted"),
        _rec(id=3, package_name="webapp", source_url="https://x/y.deb",
             status="failed"),
        _rec(id=4, package_name="ociapp", package_type="oci",
             status="oci_built"),
    ])
    monkeypatch.setattr(HD, "HistoryDB", lambda: db)
    monkeypatch.setattr(HD, "discover_tools",
                        lambda: NS(pkexec="/usr/bin/pkexec",
                                   pacman="/usr/bin/pacman"))
    d = HD.HistoryDialog()
    d.show()
    yield d, db
    d.deleteLater()


def _qmsg(monkeypatch, answers=("question",)):
    kutu = HD.QMessageBox
    log = {"question": [], "information": [], "warning": [], "critical": []}
    monkeypatch.setattr(kutu, "question",
                        staticmethod(lambda *a, **k:
                                     log["question"].append(a)
                                     or kutu.StandardButton.Yes))
    monkeypatch.setattr(kutu, "information",
                        staticmethod(lambda *a, **k:
                                     log["information"].append(a)))
    monkeypatch.setattr(kutu, "warning",
                        staticmethod(lambda *a, **k:
                                     log["warning"].append(a)))
    monkeypatch.setattr(kutu, "critical",
                        staticmethod(lambda *a, **k:
                                     log["critical"].append(a)))
    return log


def _pompala(app, kosul, sure=5.0):
    """Arka-plan QThread isleri icin olay dongusunu kosul saglanana kadar sur.

    Uretim kodu kaldirma/geri-almayi run_in_background ile yapar; testler
    callback calisana kadar beklemelidir (yoksa hem assert hem sonraki
    testin QApplication yikimi bozulur).
    """
    import time

    son = time.time() + sure
    while time.time() < son and not kosul():
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    return bool(kosul())


def test_init_populates_rows(dlg):
    d, _db = dlg
    assert d._table.rowCount() == 4


def test_search_filter_narrows(dlg):
    d, _db = dlg
    d._search_input.setText("GTK")
    d._apply_filter()
    assert d._table.rowCount() == 1


def test_type_and_status_filters(dlg):
    d, _db = dlg
    idx = d._type_filter.findData("deb")
    d._type_filter.setCurrentIndex(idx)
    d._apply_filter()
    assert d._table.rowCount() == 2  # demo + webapp (varsayilan tip deb)

    d._type_filter.setCurrentIndex(d._type_filter.findData("url"))
    d._apply_filter()
    assert d._table.rowCount() == 1  # yalniz webapp'in kaynagi var

    d._type_filter.setCurrentIndex(0)
    d._status_filter.setCurrentIndex(d._status_filter.findData("converted"))
    d._apply_filter()
    assert d._table.rowCount() == 1


def test_drag_enter_accepts_only_csv(dlg):
    d, _db = dlg
    kabul = []
    ev = NS(mimeData=lambda: NS(hasUrls=lambda: True,
                                urls=lambda: [NS(toLocalFile=lambda: "/a/b.CSV")]),
            acceptProposedAction=lambda: kabul.append(True))
    d.dragEnterEvent(ev)
    assert kabul

    ev2 = NS(mimeData=lambda: NS(hasUrls=lambda: True,
                                 urls=lambda: [NS(toLocalFile=lambda: "/a/b.txt")]))
    d.dragEnterEvent(ev2)
    assert kabul == [True]  # ikinci kabul yok


def test_drop_routes_csv_import(dlg, monkeypatch):
    d, _db = dlg
    gelen = []
    monkeypatch.setattr(d, "_import_csv", lambda p: gelen.append(p))
    ev = NS(mimeData=lambda: NS(urls=lambda: [
        NS(toLocalFile=lambda: "/a/not.csv".replace("not", "veri"))]))
    ev.mimeData().urls()[0].toLocalFile = lambda: "/a/veri.csv"
    d.dropEvent(ev)
    assert gelen and gelen[0] == Path("/a/veri.csv")


def test_export_success_writes_file(dlg, tmp_path, monkeypatch):
    d, _db = dlg
    hedef = tmp_path / "h.csv"
    monkeypatch.setattr(HD.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(hedef), "")))
    log = _qmsg(monkeypatch)
    d._export_csv()
    satir = hedef.read_text(encoding="utf-8").strip().splitlines()
    assert len(satir) == 5 and log["information"]


def test_export_cancelled_silent(dlg, tmp_path, monkeypatch):
    d, _db = dlg
    monkeypatch.setattr(HD.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    log = _qmsg(monkeypatch)
    d._export_csv()
    assert not log["information"]


def test_export_empty_selection_informs(dlg, monkeypatch):
    d, _db = dlg
    d._search_input.setText("hicbirsey")
    d._apply_filter()
    log = _qmsg(monkeypatch)
    d._export_csv()
    assert log["information"] and not log["question"]


def test_selected_name_none_without_selection(dlg, monkeypatch):
    d, _db = dlg
    log = _qmsg(monkeypatch)
    assert d._get_selected_pkg_name() is None
    assert log["warning"]


def test_uninstall_runs_pacman_remove(dlg, monkeypatch, app):
    d, _db = dlg
    d._table.selectRow(0)
    komutlar = []
    monkeypatch.setattr(HD, "safe_run",
                        lambda cmd, timeout=0: komutlar.append(cmd)
                        or NS(returncode=0, stderr=""))
    log = _qmsg(monkeypatch)
    d._uninstall_selected()
    assert _pompala(app, lambda: komutlar)
    assert any("demo" in c for c in [" ".join(k) for k in komutlar])
    assert _pompala(app, lambda: log["information"])


def test_uninstall_invalid_name_blocked(dlg, monkeypatch):
    d, _db = dlg
    d._table.selectRow(0)
    d._table.item(0, 2).setText("kotu ad!")
    _qmsg(monkeypatch)
    komutlar = []
    monkeypatch.setattr(HD, "safe_run",
                        lambda cmd, timeout=0: komutlar.append(cmd)
                        or NS(returncode=0, stderr=""))
    d._uninstall_selected()
    assert komutlar == []


def test_rollback_without_backup_warns(dlg, monkeypatch, tmp_path):
    d, db = dlg
    d._table.selectRow(0)
    db._for_package = []
    log = _qmsg(monkeypatch)
    d._rollback_selected()
    assert log["warning"]


def test_rollback_happy_and_failure_paths(dlg, monkeypatch, tmp_path, app):
    d, db = dlg
    d._table.selectRow(0)
    yedek = tmp_path / "demo-backup.pkg.tar.zst"
    yedek.write_bytes(b"b")
    db._for_package = [_rec(backup_pkg=str(yedek))]
    log = _qmsg(monkeypatch)

    monkeypatch.setattr(HD, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=0, stderr=""))
    d._rollback_selected()
    assert _pompala(app, lambda: log["information"])

    monkeypatch.setattr(HD, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=1,
                                                  stderr="pacman hatasi"))
    d._rollback_selected()
    assert _pompala(app, lambda: log["critical"])
    assert "pacman hatasi" in str(log["critical"][0])


def test_clear_history_yes_and_no(dlg, monkeypatch):
    d, db = dlg
    _qmsg(monkeypatch)
    kutu = HD.QMessageBox
    monkeypatch.setattr(kutu, "question",
                        staticmethod(lambda *a, **k: kutu.StandardButton.No))
    d._clear_history()
    assert db.cleared is False
    monkeypatch.setattr(kutu, "question",
                        staticmethod(lambda *a, **k: kutu.StandardButton.Yes))
    d._clear_history()
    assert db.cleared is True


def test_import_dialog_routes_to_import(dlg, monkeypatch, tmp_path):
    d, _db = dlg
    gelen = []
    monkeypatch.setattr(d, "_import_csv", lambda p: gelen.append(p))
    monkeypatch.setattr(HD.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("/secilen.csv", "")))
    d._import_csv_dialog()
    assert gelen == [Path("/secilen.csv")]

    monkeypatch.setattr(HD.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    d._import_csv_dialog()
    assert len(gelen) == 1


def test_import_csv_missing_file_critical(dlg, monkeypatch, tmp_path):
    d, _db = dlg
    log = _qmsg(monkeypatch)
    d._import_csv(tmp_path / "yok.csv")
    assert log["critical"]


def test_import_csv_missing_columns_critical(dlg, monkeypatch, tmp_path):
    d, _db = dlg
    f = tmp_path / "eksik.csv"
    f.write_text("ad,tur\ndemo,deb\n", encoding="utf-8")
    log = _qmsg(monkeypatch)
    d._import_csv(f)
    assert log["critical"] and "package_name" in str(log["critical"][0])


def test_import_csv_happy_counts_skips(dlg, monkeypatch, tmp_path):
    d, db = dlg
    f = tmp_path / "tam.csv"
    f.write_text(
        "package_name,package_type,original_file,source_url\n"
        "p1,deb,/x/p1.deb,\n"
        ",deb,/bos.deb,\n"
        "p2,rpm,/y/p2.rpm,https://s\n",
        encoding="utf-8")
    log = _qmsg(monkeypatch)
    onceki = len(db.added)
    d._import_csv(f)
    assert len(db.added) - onceki == 2
    assert db.added[-1]["source_url"] == "https://s"
    assert log["information"]


def test_oci_status_row_rendered(dlg):
    d, _db = dlg
    bulunan = any(d._table.item(r, 2).text() == "ociapp"
                  for r in range(d._table.rowCount()))
    assert bulunan


def test_export_type_and_status_filter_branches(dlg, tmp_path, monkeypatch):
    d, _db = dlg
    log = _qmsg(monkeypatch)
    hedef = tmp_path / "s.csv"

    d._type_filter.setCurrentIndex(d._type_filter.findData("url"))
    monkeypatch.setattr(HD.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(hedef), "")))
    d._export_csv()
    assert len(hedef.read_text(encoding="utf-8").strip().splitlines()) == 2

    d._type_filter.setCurrentIndex(d._type_filter.findData("deb"))
    monkeypatch.setattr(HD.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(hedef), "")))
    d._export_csv()          # url-olmayan tipe ait eslesme-disi continue

    d._type_filter.setCurrentIndex(0)
    d._status_filter.setCurrentIndex(d._status_filter.findData("installed"))
    d._apply_filter()
    d._export_csv()
    assert len(log["information"]) >= 3


def test_uninstall_declined_returns_silently(dlg, monkeypatch):
    d, _db = dlg
    kutu = HD.QMessageBox
    d._table.selectRow(0)
    komutlar = []
    monkeypatch.setattr(HD, "safe_run",
                        lambda cmd, timeout=0: komutlar.append(cmd)
                        or NS(returncode=0, stderr=""))
    monkeypatch.setattr(kutu, "question",
                        staticmethod(lambda *a, **k: kutu.StandardButton.No))
    d._uninstall_selected()
    assert komutlar == []


def test_rollback_declined_returns_silently(dlg, monkeypatch, tmp_path):
    d, db = dlg
    d._table.selectRow(0)
    yedek = tmp_path / "b.pkg.tar.zst"
    yedek.write_bytes(b"b")
    db._for_package = [_rec(backup_pkg=str(yedek))]
    kutu = HD.QMessageBox
    komutlar = []
    monkeypatch.setattr(HD, "safe_run",
                        lambda cmd, timeout=0: komutlar.append(cmd)
                        or NS(returncode=0, stderr=""))
    monkeypatch.setattr(kutu, "question",
                        staticmethod(lambda *a, **k: kutu.StandardButton.No))
    d._rollback_selected()
    assert komutlar == []


def test_import_csv_unreadable_path_critical(dlg, monkeypatch, tmp_path):
    d, _db = dlg
    klasor = tmp_path / "birklasor"
    klasor.mkdir()
    log = _qmsg(monkeypatch)
    d._import_csv(klasor)
    assert log["critical"]


def test_import_csv_empty_file_critical(dlg, monkeypatch, tmp_path):
    d, _db = dlg
    f = tmp_path / "bos.csv"
    f.write_text("", encoding="utf-8")
    log = _qmsg(monkeypatch)
    d._import_csv(f)
    assert log["critical"]


def test_uninstall_no_selection_returns(dlg, monkeypatch):
    d, _db = dlg
    _qmsg(monkeypatch)
    komutlar = []
    monkeypatch.setattr(HD, "safe_run",
                        lambda cmd, timeout=0: komutlar.append(cmd)
                        or NS(returncode=0, stderr=""))
    d._uninstall_selected()
    assert komutlar == []


def test_uninstall_failure_shows_critical(dlg, monkeypatch, app):
    d, _db = dlg
    d._table.selectRow(0)
    _qmsg(monkeypatch)
    monkeypatch.setattr(HD, "safe_run",
                        lambda cmd, timeout=0: NS(returncode=3,
                                                  stderr="cikaramadi"))
    log_kritik = []
    monkeypatch.setattr(HD.QMessageBox, "critical",
                        staticmethod(lambda *a, **k:
                                     log_kritik.append(a)))
    d._uninstall_selected()
    assert _pompala(app, lambda: log_kritik)
    assert "cikaramadi" in str(log_kritik[0])


def test_rollback_no_selection_returns(dlg, monkeypatch):
    d, _db = dlg
    _qmsg(monkeypatch)
    d._rollback_selected()   # secim yok -> sessiz donus


def test_import_csv_permission_error_critical(dlg, monkeypatch, tmp_path):
    d, _db = dlg
    f = tmp_path / "kilitli.csv"
    f.write_text("package_name,package_type,original_file\na,b,c\n")
    os.chmod(f, 0o000)
    log = _qmsg(monkeypatch)
    try:
        d._import_csv(f)
    finally:
        os.chmod(f, 0o644)
    assert log["critical"]
