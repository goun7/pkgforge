"""PkgForge — History & Installed Package Manager Dialog.

Provides a GUI dialog for viewing conversion history, uninstalling packages via pacman,
and rolling back to previous versions stored in local backups.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import discover_tools
from core.history_db import HistoryDB
from core.security import safe_run, is_valid_package_name
from i18n import tr

log = logging.getLogger(__name__)


class HistoryDialog(QDialog):
    """History and installed package lifecycle manager dialog."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("history.title"))
        self.setMinimumSize(740, 440)
        self._db = HistoryDB()
        self._tools = discover_tools()
        self._setup_ui()
        self._load_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header_label = QLabel(tr("history.header"))
        header_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(header_label)

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
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self._table, stretch=1)

        # Buttons
        btn_layout = QHBoxLayout()

        clear_btn = QPushButton(tr("history.clear"))
        clear_btn.clicked.connect(self._clear_history)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()

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

    def _load_data(self) -> None:
        """Load history records into table."""
        records = self._db.get_history(limit=50)
        self._table.setRowCount(len(records))

        for row, r in enumerate(records):
            self._table.setItem(row, 0, QTableWidgetItem(str(r.id or "")))
            self._table.setItem(row, 1, QTableWidgetItem(r.timestamp or ""))
            self._table.setItem(row, 2, QTableWidgetItem(r.package_name or ""))
            self._table.setItem(row, 3, QTableWidgetItem((r.package_type or "").upper()))

            status_item = QTableWidgetItem(r.status or "")
            if r.status == "success":
                status_item.setForeground(Qt.GlobalColor.green)
            else:
                status_item.setForeground(Qt.GlobalColor.red)
            self._table.setItem(row, 4, status_item)

            self._table.setItem(row, 5, QTableWidgetItem(r.original_file or ""))

    def _get_selected_pkg_name(self) -> str | None:
        selected_rows = self._table.selectionModel().selectedRows()
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
            res = safe_run([pkexec, pacman, "-R", "--noconfirm", "--", pkg_name], timeout=60)
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
            res = safe_run([pkexec, pacman, "-U", "--noconfirm", "--", str(backup_file)], timeout=120)
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
