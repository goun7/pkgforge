"""PkgForge — Paste & Download Package URL Dialog.

Provides a GUI input dialog for users to enter HTTP/HTTPS links to .deb or .rpm files.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.downloader import download_package
from i18n import tr, load_setting

log = logging.getLogger(__name__)


class UrlDialog(QDialog):
    """URL download input dialog.

    Signals:
        file_downloaded(Path) – emitted with downloaded Path when ready.
    """

    file_downloaded = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("url.title"))
        self.setMinimumWidth(520)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        info_label = QLabel(tr("url.info"))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(tr("url.placeholder"))
        layout.addWidget(self._url_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(tr("btn.cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        download_btn = QPushButton(tr("url.download_btn"))
        download_btn.setObjectName("primaryBtn")
        download_btn.clicked.connect(self._start_download)
        btn_layout.addWidget(download_btn)

        layout.addLayout(btn_layout)

    def _start_download(self) -> None:
        url = self._url_input.text().strip()
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            QMessageBox.warning(self, tr("url.title"), tr("url.invalid"))
            return

        try:
            downloaded_file = download_package(
                url, require_https=not load_setting("allow_insecure_http", False)
            )
            self.file_downloaded.emit(downloaded_file)
            self.accept()
        except Exception as exc:
            msg = tr("url.error").format(error=str(exc))
            QMessageBox.critical(self, tr("url.title"), msg)
