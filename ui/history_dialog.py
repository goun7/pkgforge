"""PkgForge — History & Installed Package Manager Dialog.

Provides a GUI dialog for viewing conversion history, uninstalling packages via pacman,
and rolling back to previous versions stored in local backups.
Now includes search/filter and CSV export.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import discover_tools
from core.history_db import HistoryDB
from core.security import is_valid_package_name, safe_run
from i18n import tr
from ui.background_worker import run_in_background

log = logging.getLogger(__name__)


class HistoryDialog(QDialog):
    """History and installed package lifecycle manager dialog.

    Supports search/filter, CSV export, CSV import, and drag-and-drop.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("history.title"))
        self.setMinimumSize(780, 480)
        self.setAcceptDrops(True)
        self._db = HistoryDB()
        self._tools = discover_tools()
        self._all_records: list = []
        self._setup_ui()
        self._load_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header_label = QLabel(tr("history.header"))
        header_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(header_label)

        # ── Search & Filter Row ──────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(tr("history.search_placeholder"))
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._search_input, stretch=2)

        self._type_filter = QComboBox()
        self._type_filter.addItem(tr("history.filter_all"), "")
        self._type_filter.addItem("DEB", "deb")
        self._type_filter.addItem("RPM", "rpm")
        self._type_filter.addItem("URL", "url")
        self._type_filter.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self._type_filter)

        self._status_filter = QComboBox()
        self._status_filter.addItem(tr("history.filter_all_status"), "")
        self._status_filter.addItem(tr("history.status_installed"), "installed")
        self._status_filter.addItem(tr("history.status_converted"), "converted")
        self._status_filter.addItem(tr("history.status_failed"), "install_failed")
        self._status_filter.addItem(tr("history.status_oci"), "oci_built")
        self._status_filter.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self._status_filter)

        layout.addLayout(filter_row)

        # ── Result count ─────────────────────────────────────────
        self._count_label = QLabel()
        self._count_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(self._count_label)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            tr("history.col_id"),
            tr("history.col_date"),
            tr("history.col_name"),
            tr("history.col_type"),
            tr("history.col_status"),
            tr("history.col_file"),
        ])
        header = self._table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        layout.addWidget(self._table, stretch=1)

        # Buttons
        btn_layout = QHBoxLayout()

        self._import_btn = QPushButton(tr("history.import_btn"))
        self._import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_btn.setToolTip(tr("history.import_tooltip"))
        self._import_btn.clicked.connect(self._import_csv_dialog)
        btn_layout.addWidget(self._import_btn)

        self._export_btn = QPushButton(tr("history.export_btn"))
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(self._export_btn)

        btn_layout.addStretch()

        clear_btn = QPushButton(tr("history.clear"))
        clear_btn.clicked.connect(self._clear_history)
        btn_layout.addWidget(clear_btn)

        self._uninstall_btn = QPushButton(tr("history.uninstall"))
        self._uninstall_btn.clicked.connect(self._uninstall_selected)
        btn_layout.addWidget(self._uninstall_btn)

        self._rollback_btn = QPushButton(tr("history.rollback"))
        self._rollback_btn.setObjectName("primaryBtn")
        self._rollback_btn.clicked.connect(self._rollback_selected)
        btn_layout.addWidget(self._rollback_btn)

        close_btn = QPushButton(tr("history.close"))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    # ── Drag & Drop ─────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        if event is None:
            return
        mime = event.mimeData()
        if mime is not None and mime.hasUrls():
            for url in mime.urls():
                if url.toLocalFile().lower().endswith(".csv"):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QDropEvent | None) -> None:
        mime = event.mimeData() if event is not None else None
        if mime is None:
            return
        for url in mime.urls():
            path = url.toLocalFile()
            if path.lower().endswith(".csv"):
                self._import_csv(Path(path))
                return

    def _load_data(self) -> None:
        """Load history records into table."""
        self._all_records = self._db.get_history(limit=100)
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Apply search and filter criteria to the table."""
        search_text = self._search_input.text().lower().strip()
        type_filter = self._type_filter.currentData() or ""
        status_filter = self._status_filter.currentData() or ""

        filtered = []
        for r in self._all_records:
            # Search filter
            if search_text:
                name = (r.package_name or "").lower()
                fname = (r.original_file or "").lower()
                if search_text not in name and search_text not in fname:
                    continue
            # Type filter
            if type_filter:
                if type_filter == "url":
                    if not r.source_url:
                        continue
                elif (r.package_type or "") != type_filter:
                    continue
            # Status filter
            if status_filter and (r.status or "") != status_filter:
                continue
            filtered.append(r)

        self._populate_table(filtered)

    def _populate_table(self, records: list) -> None:
        """Fill the table with the given records."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(records))

        for row, r in enumerate(records):
            self._table.setItem(row, 0, QTableWidgetItem(str(r.id or "")))
            self._table.setItem(row, 1, QTableWidgetItem(r.timestamp or ""))
            self._table.setItem(row, 2, QTableWidgetItem(r.package_name or ""))
            self._table.setItem(row, 3, QTableWidgetItem((r.package_type or "").upper()))

            status_item = QTableWidgetItem(r.status or "")
            if r.status in ("installed", "converted"):
                status_item.setForeground(Qt.GlobalColor.green)
            elif r.status == "oci_built":
                status_item.setForeground(Qt.GlobalColor.cyan)
            else:
                status_item.setForeground(Qt.GlobalColor.red)
            self._table.setItem(row, 4, status_item)

            self._table.setItem(row, 5, QTableWidgetItem(r.original_file or ""))

        self._table.setSortingEnabled(True)
        total = len(self._all_records)
        shown = len(records)
        if shown == total:
            self._count_label.setText(tr("history.count_total", total=total))
        else:
            self._count_label.setText(tr("history.count_shown", shown=shown, total=total))

    def _export_csv(self) -> None:
        """Export the currently filtered records to a CSV file."""
        search_text = self._search_input.text().lower().strip()
        type_filter = self._type_filter.currentData() or ""
        status_filter = self._status_filter.currentData() or ""

        # Re-apply filter to get current filtered set
        filtered = []
        for r in self._all_records:
            if search_text:
                name = (r.package_name or "").lower()
                fname = (r.original_file or "").lower()
                if search_text not in name and search_text not in fname:
                    continue
            if type_filter:
                if type_filter == "url":
                    if not r.source_url:
                        continue
                elif (r.package_type or "") != type_filter:
                    continue
            if status_filter and (r.status or "") != status_filter:
                continue
            filtered.append(r)

        if not filtered:
            QMessageBox.information(self, tr("history.title"), tr("history.no_records"))
            return

        default_name = "pkgforge_history.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, tr("history.export_title"), default_name,
            tr("history.csv_filter"),
        )
        if not path:
            return

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([tr("history.col_id"), tr("history.col_date"), tr("history.col_name"), tr("history.col_type"), tr("history.col_status"), tr("history.col_file"), "Kaynak URL"])
        for r in filtered:
            writer.writerow([
                r.id, r.timestamp, r.package_name,
                r.package_type, r.status, r.original_file,
                r.source_url or "",
            ])

        Path(path).write_text(buf.getvalue(), encoding="utf-8")
        QMessageBox.information(
            self, tr("history.exported_title"),
            tr("history.exported_msg").format(count=len(filtered), path=path),
        )

    def _get_selected_pkg_name(self) -> str | None:
        sel_model = self._table.selectionModel()
        selected_rows = sel_model.selectedRows() if sel_model is not None else []
        if not selected_rows:
            QMessageBox.warning(self, tr("common.warning"), tr("history.select_warning"))
            return None
        row = selected_rows[0].row()
        item = self._table.item(row, 2)
        return item.text() if item else None

    def _uninstall_selected(self) -> None:
        pkg_name = self._get_selected_pkg_name()
        if not pkg_name:
            return

        msg = tr("history.confirm_uninstall").format(name=pkg_name)
        reply = QMessageBox.question(
            self,
            tr("history.uninstall"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if not is_valid_package_name(pkg_name):
                QMessageBox.critical(self, tr("common.error"), tr("common.invalid_pkg_name").format(name=pkg_name))
                return
            pkexec = self._tools.pkexec or "pkexec"
            pacman = self._tools.pacman or "pacman"
            cmd = [pkexec, pacman, "-R", "--noconfirm", "--", pkg_name]
            run_in_background(
                lambda: safe_run(cmd, timeout=60),
                on_done=lambda res: self._on_uninstall_done(pkg_name, res),
                on_error=self._show_error,
            )

    def _show_error(self, err: str) -> None:
        QMessageBox.critical(self, tr("common.error"), err)

    def _on_uninstall_done(self, pkg_name: str, res: Any) -> None:
        if res.returncode == 0:
            QMessageBox.information(self, tr("common.success"), tr("history.msg_uninstalled").format(name=pkg_name))
            self._load_data()
        else:
            QMessageBox.critical(self, tr("common.error"), tr("history.msg_uninstall_failed").format(error=res.stderr))

    def _rollback_selected(self) -> None:
        pkg_name = self._get_selected_pkg_name()
        if not pkg_name:
            return

        records = self._db.get_records_for_package(pkg_name)
        backups = [r for r in records if r.backup_pkg and Path(r.backup_pkg).is_file()]

        if not backups:
            QMessageBox.warning(self, tr("common.warning"), tr("history.no_backup").format(name=pkg_name))
            return

        backup_file = Path(backups[0].backup_pkg)
        msg = tr("history.confirm_rollback").format(name=pkg_name, backup=backup_file.name)
        reply = QMessageBox.question(
            self,
            tr("history.rollback"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            pkexec = self._tools.pkexec or "pkexec"
            pacman = self._tools.pacman or "pacman"
            cmd = [pkexec, pacman, "-U", "--noconfirm", "--", str(backup_file)]
            run_in_background(
                lambda: safe_run(cmd, timeout=120),
                on_done=lambda res: self._on_rollback_done(pkg_name, res),
                on_error=self._show_error,
            )

    def _on_rollback_done(self, pkg_name: str, res: Any) -> None:
        if res.returncode == 0:
            QMessageBox.information(self, tr("common.success"), tr("history.msg_rolled_back").format(name=pkg_name))
            self._load_data()
        else:
            QMessageBox.critical(self, tr("common.error"), tr("history.msg_rollback_failed").format(error=res.stderr))

    def _clear_history(self) -> None:
        reply = QMessageBox.question(
            self,
            tr("history.clear"),
            tr("history.confirm_clear"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.clear_history()
            self._load_data()

    # ── CSV Import ──────────────────────────────────────────────

    def _import_csv_dialog(self) -> None:
        """Open file chooser for CSV import."""
        path, _ = QFileDialog.getOpenFileName(
            self, tr("history.import_title"), "",
            tr("history.csv_filter"),
        )
        if path:
            self._import_csv(Path(path))

    def _import_csv(self, csv_path: Path) -> None:
        """Import package list from a CSV file.

        Expected CSV columns: package_name, package_type, original_file, source_url
        The import creates history records so the user can later track/rollback.
        """
        if not csv_path.is_file():
            QMessageBox.critical(self, tr("common.error"), tr("history.csv_not_found").format(path=csv_path))
            return

        try:
            content = csv_path.read_text(encoding="utf-8")
            reader = csv.DictReader(io.StringIO(content))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("common.error"), tr("history.csv_read_error").format(error=exc))
            return

        imported = 0
        skipped = 0
        required_cols = {"package_name", "package_type", "original_file"}
        if reader.fieldnames is None:
            QMessageBox.critical(self, tr("common.error"), tr("history.csv_empty"))
            return

        missing_cols = required_cols - set(reader.fieldnames)
        if missing_cols:
            QMessageBox.critical(
                self, tr("common.error"),
                tr("history.import_missing_cols").format(missing=', '.join(missing_cols)),
            )
            return

        for row in reader:
            name = (row.get("package_name") or "").strip()
            ptype = (row.get("package_type") or "").strip()
            orig = (row.get("original_file") or "").strip()
            url = (row.get("source_url") or "").strip()

            if not name or not ptype:
                skipped += 1
                continue

            self._db.add_record(
                package_name=name,
                original_file=orig,
                package_type=ptype,
                sha256="",
                status="imported",
                output_pkg="",
                source_url=url,
            )
            imported += 1

        self._load_data()
        msg = tr("history.import_result").format(imported=imported)
        if skipped:
            msg += tr("history.import_skipped").format(skipped=skipped)
        QMessageBox.information(self, tr("history.import_result_title"), msg)
