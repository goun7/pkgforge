"""PkgForge — About Dialog.

Shows version, license, and project information.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from config import APP_NAME, APP_VERSION
from i18n import tr
from ui.styles import get_colors


class AboutDialog(QDialog):
    """About dialog showing project information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("about.title"))
        self.setMinimumWidth(420)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel(f"📦 {APP_NAME}")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {get_colors().TEAL};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Version
        version = QLabel(tr("about.version").format(version=APP_VERSION))
        version.setStyleSheet(f"font-size: 14px; color: {get_colors().TEXT_DIM};")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        # Description
        desc = QLabel(tr("about.desc_long"))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"color: {get_colors().TEXT}; font-size: 13px;")
        layout.addWidget(desc)

        # Info
        info_layout = QHBoxLayout()
        info_layout.setSpacing(20)

        info_items = [
            (tr("about.license_label"), "GPL-3.0-or-later"),
            (tr("about.python_label"), "3.10+"),
            (tr("about.platform_label"), "Linux"),
        ]
        for label, value in info_items:
            col = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {get_colors().TEXT_MUTED}; font-size: 11px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet(f"color: {get_colors().TEXT}; font-size: 13px; font-weight: bold;")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val)
            info_layout.addLayout(col)

        layout.addLayout(info_layout)

        # Links
        links = QLabel(
            '<a href="https://github.com/goun7/pkgforge" style="color: ' +
            get_colors().TEAL + ';">GitHub</a> · '
            '<a href="https://github.com/goun7/pkgforge/blob/master/LICENSE" style="color: ' +
            get_colors().TEAL + ';">' + tr("about.license_label") + '</a>'
        )
        links.setOpenExternalLinks(True)
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(links)

        # Close button
        close_btn = QPushButton(tr("about.close"))
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(
            f"background-color: {get_colors().SURFACE_ALT}; color: {get_colors().TEXT}; "
            f"padding: 8px 24px; border-radius: 4px;"
        )
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
