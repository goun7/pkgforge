"""Tur-63 — PyQt6 Feature Tezgahi Faz 2 (scan/attest/publish/snapshot)."""
from __future__ import annotations

import os
from typing import ClassVar

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication, QFileDialog

import ui.tools_dialog as TD
from ui.tools_dialog import ToolsDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def td(app, monkeypatch):
    import core.snapshot_cleanup as SC
    monkeypatch.setattr(SC, "get_cleanup_status",
                        lambda: {"installed": False, "active": False,
                                 "next_run": "", "last_run": ""})
    d = ToolsDialog()
    yield d
    d.deleteLater()


@pytest.fixture()
def sync_bg(monkeypatch):
    def run(fn, on_done=None, on_error=None):
        try:
            result = fn()
            if on_done:
                on_done(result)
        except Exception as e:  # noqa: BLE001
            if on_error:
                on_error(str(e))

    monkeypatch.setattr(TD, "run_in_background", run)


def _onayla_kaldirma(monkeypatch):
    """Uretimdeki QMessageBox.question modalini Yes ile yanitla.

    Kaldirma artik yikici-islem onayi ister; mock'suz test modalda
    sonsuza dek bloklanir (offscreen dahil).
    """
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )


def test_seven_tabs(td):
    assert td._tabs.count() == 7


# ── Scan ────────────────────────────────────────────────────────
def test_scan_missing_file(td, sync_bg):
    td._scan_path.setText("")
    td._run_scan_image()
    assert "❌" in td._scan_result.toPlainText()


def test_scan_clean(td, sync_bg, monkeypatch, tmp_path):
    img = tmp_path / "img.tar"
    img.write_bytes(b"x")
    td._scan_path.setText(str(img))
    import core.malware_scanner as MS
    monkeypatch.setattr(MS, "scan_oci_image",
                        lambda p: {"clean": True, "findings": [], "detail": "temiz"})
    td._run_scan_image()
    assert "temiz" in td._scan_result.toPlainText()
    assert td._scan_btn.isEnabled()


def test_scan_findings(td, sync_bg, monkeypatch, tmp_path):
    img = tmp_path / "img.tar"
    img.write_bytes(b"x")
    td._scan_path.setText(str(img))
    import core.malware_scanner as MS
    monkeypatch.setattr(MS, "scan_oci_image", lambda p: {
        "clean": False, "detail": "1 bulgu",
        "findings": [{"tool": "trivy", "severity": "HIGH", "line": "cve"}]})
    td._run_scan_image()
    text = td._scan_result.toPlainText()
    assert "trivy" in text and "cve" in text


def test_scan_error(td, sync_bg, monkeypatch, tmp_path):
    img = tmp_path / "img.tar"
    img.write_bytes(b"x")
    td._scan_path.setText(str(img))
    import core.malware_scanner as MS

    def boom(p):
        raise RuntimeError("scan patladi")

    monkeypatch.setattr(MS, "scan_oci_image", boom)
    td._run_scan_image()
    assert "scan patladi" in td._scan_result.toPlainText()


def test_pick_scan(td, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("/x/img.tar", "")))
    td._pick_scan()
    assert td._scan_path.text() == "/x/img.tar"


# ── Attest ──────────────────────────────────────────────────────
class _FakeAtt:
    subject: ClassVar[list] = [{"name": "p.pkg.tar.zst"}]


def test_attest_missing_file(td, sync_bg):
    td._attest_path.setText("")
    td._run_attest()
    assert "❌" in td._attest_result.text()


def test_attest_success(td, sync_bg, monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    td._attest_path.setText(str(pkg))
    import core.provenance as PR
    monkeypatch.setattr(PR, "find_provenance", lambda p: tmp_path / "p.prov")
    monkeypatch.setattr(PR, "load_provenance", lambda p: object())
    monkeypatch.setattr(PR, "create_attestation", lambda prov: _FakeAtt())
    monkeypatch.setattr(PR, "save_attestation", lambda att, path: path)
    td._run_attest()
    assert "p.pkg.tar.zst" in td._attest_result.text()
    assert td._attest_btn.isEnabled()


def test_attest_no_provenance(td, sync_bg, monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    td._attest_path.setText(str(pkg))
    import core.provenance as PR
    monkeypatch.setattr(PR, "find_provenance", lambda p: None)
    td._run_attest()
    assert "❌" in td._attest_result.text()


# ── Publish ─────────────────────────────────────────────────────
class _FakeAUR:
    def __init__(self, tmp_path):
        self.pkgbuild = tmp_path / "aur" / "PKGBUILD"
        self.name = "p-bin"


def test_publish_missing_file(td, sync_bg):
    td._publish_path.setText("")
    td._run_publish()
    assert "❌" in td._publish_result.text()


def test_publish_success(td, sync_bg, monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    td._publish_path.setText(str(pkg))
    import core.aur_publish as AP
    monkeypatch.setattr(AP, "prepare_aur_package",
                        lambda p, o: (True, "hazir", _FakeAUR(tmp_path)))
    td._run_publish()
    text = td._publish_result.text()
    assert "hazir" in text and "PKGBUILD" in text


def test_publish_prepare_fails(td, sync_bg, monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    td._publish_path.setText(str(pkg))
    import core.aur_publish as AP
    monkeypatch.setattr(AP, "prepare_aur_package",
                        lambda p, o: (False, "hata", None))
    td._run_publish()
    assert "❌" in td._publish_result.text()


# ── Snapshot ────────────────────────────────────────────────────
def test_snapshot_status_not_installed(td):
    assert "❌" in td._snapshot_status.text()


def test_snapshot_status_installed(app, monkeypatch):
    import core.snapshot_cleanup as SC
    monkeypatch.setattr(SC, "get_cleanup_status",
                        lambda: {"installed": True, "active": True,
                                 "next_run": "yarin", "last_run": ""})
    d = ToolsDialog()
    assert "kurulu" in d._snapshot_status.text()
    assert "yarin" in d._snapshot_status.text()
    d.deleteLater()


def test_snapshot_install(td, sync_bg, monkeypatch):
    import core.snapshot_cleanup as SC
    monkeypatch.setattr(SC, "install_cleanup_service",
                        lambda max_age_days=7: (True, "kuruldu"))
    td._run_snapshot_install()
    assert "kuruldu" in td._snapshot_status.text()
    assert td._snap_install_btn.isEnabled()


def test_snapshot_remove(td, sync_bg, monkeypatch):
    import core.snapshot_cleanup as SC
    monkeypatch.setattr(SC, "remove_cleanup_service",
                        lambda: (True, "kaldirildi"))
    _onayla_kaldirma(monkeypatch)
    td._run_snapshot_remove()
    assert "kaldirildi" in td._snapshot_status.text()
    assert td._snap_remove_btn.isEnabled()


def test_pick_attest(td, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("/x/p.pkg.tar.zst", "")))
    td._pick_attest()
    assert td._attest_path.text() == "/x/p.pkg.tar.zst"


def test_attest_load_fails(td, sync_bg, monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    td._attest_path.setText(str(pkg))
    import core.provenance as PR
    monkeypatch.setattr(PR, "find_provenance", lambda p: tmp_path / "p.prov")
    monkeypatch.setattr(PR, "load_provenance", lambda p: None)
    td._run_attest()
    assert "❌" in td._attest_result.text()


def test_attest_error(td, sync_bg, monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    td._attest_path.setText(str(pkg))
    import core.provenance as PR
    monkeypatch.setattr(PR, "find_provenance", lambda p: tmp_path / "p.prov")
    monkeypatch.setattr(PR, "load_provenance", lambda p: object())

    def boom(prov):
        raise RuntimeError("attest patladi")

    monkeypatch.setattr(PR, "create_attestation", boom)
    td._run_attest()
    assert "attest patladi" in td._attest_result.text()


def test_pick_publish(td, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("/x/p.pkg.tar.zst", "")))
    td._pick_publish()
    assert td._publish_path.text() == "/x/p.pkg.tar.zst"


def test_publish_error(td, sync_bg, monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"x")
    td._publish_path.setText(str(pkg))
    import core.aur_publish as AP

    def boom(p, o):
        raise RuntimeError("publish patladi")

    monkeypatch.setattr(AP, "prepare_aur_package", boom)
    td._run_publish()
    assert "publish patladi" in td._publish_result.text()


def test_snapshot_install_error(td, sync_bg, monkeypatch):
    import core.snapshot_cleanup as SC

    def boom(max_age_days=7):
        raise RuntimeError("install patladi")

    monkeypatch.setattr(SC, "install_cleanup_service", boom)
    td._run_snapshot_install()
    assert "install patladi" in td._snapshot_status.text()


def test_snapshot_remove_error(td, sync_bg, monkeypatch):
    import core.snapshot_cleanup as SC

    def boom():
        raise RuntimeError("remove patladi")

    monkeypatch.setattr(SC, "remove_cleanup_service", boom)
    _onayla_kaldirma(monkeypatch)
    td._run_snapshot_remove()
    assert "remove patladi" in td._snapshot_status.text()

