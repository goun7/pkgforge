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
    """Feature Tezgahi: uc sekme (RPM->DEB, ABI, Audit)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("tools.title"))
        self.resize(680, 500)
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)
        self._tabs.addTab(self._build_rpm_tab(), tr("tools.rpm_tab"))
        self._tabs.addTab(self._build_abi_tab(), tr("tools.abi_tab"))
        self._tabs.addTab(self._build_audit_tab(), tr("tools.audit_tab"))

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
