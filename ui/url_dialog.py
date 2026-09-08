"""PkgForge — Paste & Download Package URL Dialog.

Provides a GUI input dialog for users to enter HTTP/HTTPS links to .deb or .rpm files.
"""

from __future__ import annotations

import logging
from typing import Any

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
from i18n import load_setting, tr

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

        self._download_btn = QPushButton(tr("url.download_btn"))
        self._download_btn.setObjectName("primaryBtn")
        self._download_btn.clicked.connect(self._start_download)
        btn_layout.addWidget(self._download_btn)

        layout.addLayout(btn_layout)

    def _start_download(self) -> None:
        url = self._url_input.text().strip()
        if not url or not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, tr("url.title"), tr("url.invalid"))
            return

        # Download on a background thread so the GUI stays responsive.
        # Previously this ran synchronously and froze the dialog for the
        # whole download.
        from ui.background_worker import run_in_background

        self._download_btn.setEnabled(False)
        self._download_btn.setText(tr("url.downloading"))

        def _do_download() -> Any:
            return download_package(
                url, require_https=not load_setting("allow_insecure_http", False)
            )

        def _on_done(downloaded_file: Any) -> None:
            self.file_downloaded.emit(downloaded_file)
            self.accept()

        def _on_error(err_msg: str) -> None:
            self._download_btn.setEnabled(True)
            self._download_btn.setText(tr("url.download_btn"))
            msg = tr("url.error").format(error=err_msg)
            QMessageBox.critical(self, tr("url.title"), msg)

        run_in_background(_do_download, on_done=_on_done, on_error=_on_error)
