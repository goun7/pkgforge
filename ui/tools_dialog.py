"""PkgForge — Feature Tezgahi: RPM->DEB, ABI Check, Audit araclari (PyQt6).

CLI'daki rpm-to-deb / abi-check / audit komutlarinin GUI karsiligi.
Uc sekme; her biri ilgili core fonksiyonunu arka planda calistirir.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from i18n import tr
from ui.background_worker import run_in_background


class ToolsDialog(QDialog):
    """Feature Tezgahi: RPM->DEB, ABI, Audit + Faz 2 aracları."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("tools.title"))
        self.resize(680, 520)
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)
        self._tabs.addTab(self._build_rpm_tab(), tr("tools.rpm_tab"))
        self._tabs.addTab(self._build_abi_tab(), tr("tools.abi_tab"))
        self._tabs.addTab(self._build_audit_tab(), tr("tools.audit_tab"))
        self._tabs.addTab(self._build_scan_tab(), tr("tools.scan_tab"))
        self._tabs.addTab(self._build_attest_tab(), tr("tools.attest_tab"))
        self._tabs.addTab(self._build_publish_tab(), tr("tools.publish_tab"))
        self._tabs.addTab(self._build_snapshot_tab(), tr("tools.snapshot_tab"))

    # ── RPM -> DEB ──────────────────────────────────────────────
    def _build_rpm_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self._rpm_path = QLineEdit()
        self._rpm_path.setPlaceholderText(tr("tools.rpm_placeholder"))
        browse = QPushButton(tr("tools.browse"))
        browse.clicked.connect(self._pick_rpm)
        row.addWidget(self._rpm_path)
        row.addWidget(browse)
        lay.addLayout(row)
        self._rpm_btn = QPushButton(tr("tools.rpm_convert"))
        self._rpm_btn.clicked.connect(self._run_rpm_to_deb)
        lay.addWidget(self._rpm_btn)
        self._rpm_result = QLabel("")
        self._rpm_result.setWordWrap(True)
        lay.addWidget(self._rpm_result)
        lay.addStretch()
        return w

    def _pick_rpm(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("tools.rpm_pick"), "", "RPM (*.rpm)")
        if path:
            self._rpm_path.setText(path)

    def _run_rpm_to_deb(self) -> None:
        from core.rpm_to_deb_converter import (
            is_rpm_to_deb_available,
            rpm_to_deb,
        )
        rpm = self._rpm_path.text().strip()
        if not rpm or not Path(rpm).is_file():
            self._rpm_result.setText(tr("tools.file_missing"))
            return
        self._rpm_btn.setEnabled(False)
        self._rpm_result.setText(tr("tools.running"))

        def _op():
            if not is_rpm_to_deb_available():
                return {"ok": False, "message": tr("tools.rpm_tools_missing"),
                        "deb_path": ""}
            ok, msg, deb = rpm_to_deb(Path(rpm), Path.cwd())
            return {"ok": ok, "message": msg,
                    "deb_path": str(deb) if deb else ""}

        def _done(res) -> None:
            self._rpm_btn.setEnabled(True)
            icon = "✅" if res["ok"] else "❌"
            text = f"{icon} {res['message']}"
            if res.get("deb_path"):
                text += f" -> {res['deb_path']}"
            self._rpm_result.setText(text)

        def _err(msg: str) -> None:
            self._rpm_btn.setEnabled(True)
            self._rpm_result.setText(f"❌ {msg}")

        run_in_background(_op, _done, _err)

    # ── ABI Check ───────────────────────────────────────────────
    def _build_abi_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self._abi_path = QLineEdit()
        self._abi_path.setPlaceholderText(tr("tools.abi_placeholder"))
        browse = QPushButton(tr("tools.browse"))
        browse.clicked.connect(self._pick_abi)
        row.addWidget(self._abi_path)
        row.addWidget(browse)
        lay.addLayout(row)
        self._abi_btn = QPushButton(tr("tools.abi_scan"))
        self._abi_btn.clicked.connect(self._run_abi_check)
        lay.addWidget(self._abi_btn)
        self._abi_result = QPlainTextEdit()
        self._abi_result.setReadOnly(True)
        lay.addWidget(self._abi_result)
        return w

    def _pick_abi(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("tools.abi_pick"), "", tr("tools.pkg_filter"))
        if path:
            self._abi_path.setText(path)

    def _run_abi_check(self) -> None:
        from core.abi_scanner import check_abi_compatibility
        pkg = self._abi_path.text().strip()
        if not pkg or not Path(pkg).is_file():
            self._abi_result.setPlainText(tr("tools.file_missing"))
            return
        self._abi_btn.setEnabled(False)
        self._abi_result.setPlainText(tr("tools.running"))

        def _op():
            return check_abi_compatibility(Path(pkg))

        def _done(report) -> None:
            self._abi_btn.setEnabled(True)
            head = tr("tools.abi_passed") if report.passed else tr("tools.abi_failed")
            self._abi_result.setPlainText(f"{head}\n\n{report.summary()}")

        def _err(msg: str) -> None:
            self._abi_btn.setEnabled(True)
            self._abi_result.setPlainText(f"❌ {msg}")

        run_in_background(_op, _done, _err)

    # ── Audit ───────────────────────────────────────────────────
    def _build_audit_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self._audit_btn = QPushButton(tr("tools.audit_load"))
        self._audit_btn.clicked.connect(self._run_audit)
        lay.addWidget(self._audit_btn)
        self._audit_summary = QLabel("")
        self._audit_summary.setWordWrap(True)
        lay.addWidget(self._audit_summary)
        self._audit_detail = QPlainTextEdit()
        self._audit_detail.setReadOnly(True)
        lay.addWidget(self._audit_detail)
        return w

    def _run_audit(self) -> None:
        from core.history_db import HistoryDB
        self._audit_btn.setEnabled(False)
        self._audit_detail.setPlainText(tr("tools.running"))

        def _op():
            records = HistoryDB().get_history(limit=100)
            status_counts: dict[str, int] = {}
            type_counts: dict[str, int] = {}
            for r in records:
                status_counts[r.status] = status_counts.get(r.status, 0) + 1
                type_counts[r.package_type] = type_counts.get(r.package_type, 0) + 1
            integrity = sum(
                1 for r in records
                if (r.output_pkg and not Path(r.output_pkg).exists())
                or (r.backup_pkg and not Path(r.backup_pkg).exists())
            )
            return {"total": len(records), "status_counts": status_counts,
                    "type_counts": type_counts, "integrity": integrity,
                    "records": records}

        def _done(res) -> None:
            self._audit_btn.setEnabled(True)
            self._audit_summary.setText(
                tr("tools.audit_summary", total=res["total"],
                   integrity=res["integrity"]))
            lines = []
            for status, count in sorted(res["status_counts"].items()):
                lines.append(f"{status}: {count}")
            lines.append("")
            for r in res["records"][:50]:
                lines.append(
                    f"[{r.timestamp}] {r.package_name} ({r.package_type}) -> {r.status}")
            self._audit_detail.setPlainText("\n".join(lines))

        def _err(msg: str) -> None:
            self._audit_btn.setEnabled(True)
            self._audit_detail.setPlainText(f"❌ {msg}")

        run_in_background(_op, _done, _err)

    # ── Scan Image (Faz 2) ─────────────────────────────────────
    def _build_scan_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self._scan_path = QLineEdit()
        self._scan_path.setPlaceholderText(tr("tools.scan_placeholder"))
        browse = QPushButton(tr("tools.browse"))
        browse.clicked.connect(self._pick_scan)
        row.addWidget(self._scan_path)
        row.addWidget(browse)
        lay.addLayout(row)
        self._scan_btn = QPushButton(tr("tools.scan_run"))
        self._scan_btn.clicked.connect(self._run_scan_image)
        lay.addWidget(self._scan_btn)
        self._scan_result = QPlainTextEdit()
        self._scan_result.setReadOnly(True)
        lay.addWidget(self._scan_result)
        return w

    def _pick_scan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("tools.scan_pick"), "", "")
        if path:
            self._scan_path.setText(path)

    def _run_scan_image(self) -> None:
        from core.malware_scanner import scan_oci_image
        img = self._scan_path.text().strip()
        if not img or not Path(img).exists():
            self._scan_result.setPlainText(tr("tools.file_missing"))
            return
        self._scan_btn.setEnabled(False)
        self._scan_result.setPlainText(tr("tools.running"))

        def _op():
            return scan_oci_image(Path(img))

        def _done(res) -> None:
            self._scan_btn.setEnabled(True)
            head = tr("tools.scan_clean") if res["clean"] else tr("tools.scan_findings")
            lines = [head, res["detail"], ""]
            for f in res["findings"][:20]:
                lines.append(f"[{f['tool']}/{f['severity']}] {f['line']}")
            self._scan_result.setPlainText("\n".join(lines))

        def _err(msg: str) -> None:
            self._scan_btn.setEnabled(True)
            self._scan_result.setPlainText(f"❌ {msg}")

        run_in_background(_op, _done, _err)

    # ── Attest (Faz 2) ─────────────────────────────────────────
    def _build_attest_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self._attest_path = QLineEdit()
        self._attest_path.setPlaceholderText(tr("tools.attest_placeholder"))
        browse = QPushButton(tr("tools.browse"))
        browse.clicked.connect(self._pick_attest)
        row.addWidget(self._attest_path)
        row.addWidget(browse)
        lay.addLayout(row)
        self._attest_btn = QPushButton(tr("tools.attest_run"))
        self._attest_btn.clicked.connect(self._run_attest)
        lay.addWidget(self._attest_btn)
        self._attest_result = QLabel("")
        self._attest_result.setWordWrap(True)
        lay.addWidget(self._attest_result)
        lay.addStretch()
        return w

    def _pick_attest(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("tools.attest_pick"), "", tr("tools.pkg_filter"))
        if path:
            self._attest_path.setText(path)

    def _run_attest(self) -> None:
        from core.provenance import (
            create_attestation,
            find_provenance,
            load_provenance,
            save_attestation,
        )
        pkg = self._attest_path.text().strip()
        if not pkg or not Path(pkg).is_file():
            self._attest_result.setText(tr("tools.file_missing"))
            return
        self._attest_btn.setEnabled(False)
        self._attest_result.setText(tr("tools.running"))

        def _op():
            pkg_path = Path(pkg)
            prov_path = find_provenance(pkg_path)
            if not prov_path:
                return {"ok": False, "error": tr("tools.attest_no_prov")}
            prov = load_provenance(prov_path)
            if not prov:
                return {"ok": False, "error": tr("tools.attest_load_fail")}
            att = create_attestation(prov)
            att_path = save_attestation(
                att, pkg_path.parent / f"{pkg_path.name}.attestation.json")
            subject = att.subject[0].get("name", "") if att.subject else ""
            return {"ok": True, "path": str(att_path), "subject": subject}

        def _done(res) -> None:
            self._attest_btn.setEnabled(True)
            if res["ok"]:
                self._attest_result.setText(
                    f"✅ {res['subject']}\n{res['path']}")
            else:
                self._attest_result.setText(f"❌ {res['error']}")

        def _err(msg: str) -> None:
            self._attest_btn.setEnabled(True)
            self._attest_result.setText(f"❌ {msg}")

        run_in_background(_op, _done, _err)

    # ── Publish (Faz 2) ────────────────────────────────────────
    def _build_publish_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self._publish_path = QLineEdit()
        self._publish_path.setPlaceholderText(tr("tools.publish_placeholder"))
        browse = QPushButton(tr("tools.browse"))
        browse.clicked.connect(self._pick_publish)
        row.addWidget(self._publish_path)
        row.addWidget(browse)
        lay.addLayout(row)
        self._publish_btn = QPushButton(tr("tools.publish_run"))
        self._publish_btn.clicked.connect(self._run_publish)
        lay.addWidget(self._publish_btn)
        self._publish_result = QLabel("")
        self._publish_result.setWordWrap(True)
        lay.addWidget(self._publish_result)
        lay.addStretch()
        return w

    def _pick_publish(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("tools.publish_pick"), "", tr("tools.pkg_filter"))
        if path:
            self._publish_path.setText(path)

    def _run_publish(self) -> None:
        from core.aur_publish import prepare_aur_package
        pkg = self._publish_path.text().strip()
        if not pkg or not Path(pkg).is_file():
            self._publish_result.setText(tr("tools.file_missing"))
            return
        self._publish_btn.setEnabled(False)
        self._publish_result.setText(tr("tools.running"))

        def _op():
            ok, msg, aur_pkg = prepare_aur_package(Path(pkg), Path.cwd())
            if not ok or not aur_pkg:
                return {"ok": False, "message": msg}
            return {"ok": True, "message": msg, "name": aur_pkg.name,
                    "pkgbuild": str(aur_pkg.pkgbuild)}

        def _done(res) -> None:
            self._publish_btn.setEnabled(True)
            icon = "✅" if res["ok"] else "❌"
            text = f"{icon} {res['message']}"
            if res.get("pkgbuild"):
                text += f"\nPKGBUILD: {res['pkgbuild']}"
            self._publish_result.setText(text)

        def _err(msg: str) -> None:
            self._publish_btn.setEnabled(True)
            self._publish_result.setText(f"❌ {msg}")

        run_in_background(_op, _done, _err)

    # ── Snapshot Cleanup (Faz 2) ───────────────────────────────
    def _build_snapshot_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self._snapshot_status = QLabel("")
        self._snapshot_status.setWordWrap(True)
        lay.addWidget(self._snapshot_status)
        row = QHBoxLayout()
        self._snap_refresh_btn = QPushButton(tr("tools.snapshot_refresh"))
        self._snap_refresh_btn.clicked.connect(self._run_snapshot_status)
        self._snap_install_btn = QPushButton(tr("tools.snapshot_install"))
        self._snap_install_btn.clicked.connect(self._run_snapshot_install)
        self._snap_remove_btn = QPushButton(tr("tools.snapshot_remove"))
        self._snap_remove_btn.clicked.connect(self._run_snapshot_remove)
        row.addWidget(self._snap_refresh_btn)
        row.addWidget(self._snap_install_btn)
        row.addWidget(self._snap_remove_btn)
        lay.addLayout(row)
        lay.addStretch()
        self._run_snapshot_status()
        return w

    def _run_snapshot_status(self) -> None:
        from core.snapshot_cleanup import get_cleanup_status
        status = get_cleanup_status()
        if status["installed"]:
            active = (tr("tools.snapshot_active") if status["active"]
                      else tr("tools.snapshot_stopped"))
            text = tr("tools.snapshot_installed", active=active)
            if status.get("next_run"):
                text += f"\n{tr('tools.snapshot_next')}: {status['next_run']}"
        else:
            text = tr("tools.snapshot_not_installed")
        self._snapshot_status.setText(text)

    def _run_snapshot_install(self) -> None:
        from core.snapshot_cleanup import install_cleanup_service
        self._snap_install_btn.setEnabled(False)

        def _op():
            ok, msg = install_cleanup_service(max_age_days=7)
            return {"ok": ok, "message": msg}

        def _done(res) -> None:
            self._snap_install_btn.setEnabled(True)
            icon = "✅" if res["ok"] else "❌"
            self._snapshot_status.setText(f"{icon} {res['message']}")

        def _err(msg: str) -> None:
            self._snap_install_btn.setEnabled(True)
            self._snapshot_status.setText(f"❌ {msg}")

        run_in_background(_op, _done, _err)

    def _run_snapshot_remove(self) -> None:
        from core.snapshot_cleanup import remove_cleanup_service
        self._snap_remove_btn.setEnabled(False)

        def _op():
            ok, msg = remove_cleanup_service()
            return {"ok": ok, "message": msg}

        def _done(res) -> None:
            self._snap_remove_btn.setEnabled(True)
            icon = "✅" if res["ok"] else "❌"
            self._snapshot_status.setText(f"{icon} {res['message']}")

        def _err(msg: str) -> None:
            self._snap_remove_btn.setEnabled(True)
            self._snapshot_status.setText(f"❌ {msg}")

        run_in_background(_op, _done, _err)
