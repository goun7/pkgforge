"""PkgForge — Drag-and-drop zone widget.

Accepts single or multiple .deb and .rpm files via drag-and-drop
or file picker dialog. Provides animated visual feedback.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from i18n import tr
from ui.resources.icons import DROP_ICON, DROP_ICON_ACTIVE

_ACCEPTED_SUFFIXES = {".deb", ".rpm"}


class DropZone(QWidget):
    """Drag-and-drop area for package files.

    Signals:
        files_dropped(list[Path]) – emitted when valid files are dropped or selected.
    """

    files_dropped = pyqtSignal(list)  # list[Path]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(220)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        # Drop icon
        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedSize(72, 72)
        self._set_icon(DROP_ICON)
        layout.addWidget(self._icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Main label
        self._main_label = QLabel(tr("drop.hint"))
        self._main_label.setObjectName("dropLabel")
        self._main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._main_label)

        # Sub label
        self._sub_label = QLabel(tr("drop.or"))
        self._sub_label.setObjectName("dropSubLabel")
        self._sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._sub_label)

        # File picker button
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._pick_btn = QPushButton(tr("drop.pick_multi"))
        self._pick_btn.setObjectName("primaryBtn")
        self._pick_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pick_btn.setFixedWidth(200)
        self._pick_btn.setAccessibleName(tr("drop.pick_multi"))
        self._pick_btn.setAccessibleDescription(".deb veya .rpm dosyalarını seçmek için dosya teşekkürü açar")
        self._pick_btn.clicked.connect(self._on_pick_file)
        btn_layout.addWidget(self._pick_btn)

        layout.addLayout(btn_layout)

        # Supported formats hint
        hint = QLabel(tr("drop.supported"))
        hint.setObjectName("dropSubLabel")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    def _set_icon(self, svg_data: str) -> None:
        """Update the drop zone icon."""
        self._icon_label.setText("")
        from PyQt6.QtGui import QPainter, QPixmap
        from PyQt6.QtSvg import QSvgRenderer

        renderer = QSvgRenderer(svg_data.encode("utf-8"))
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self._icon_label.setPixmap(pixmap)

    # ── Drag & Drop ──────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        if event is None:
            return
        mime = event.mimeData()
        if mime is not None and mime.hasUrls():
            for url in mime.urls():
                path = Path(url.toLocalFile())
                if path.suffix.lower() in _ACCEPTED_SUFFIXES:
                    event.acceptProposedAction()
                    self.setProperty("dragActive", True)
                    style = self.style()
                    if style is not None:
                        style.unpolish(self)
                        style.polish(self)
                    self._set_icon(DROP_ICON_ACTIVE)
                    self._main_label.setText(tr("drop.active"))
                    return
        event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent | None) -> None:
        self._reset_drop_state()
        if event is not None:
            event.accept()

    def dropEvent(self, event: QDropEvent | None) -> None:
        self._reset_drop_state()
        if event is None:
            return

        mime = event.mimeData()
        if mime is None or not mime.hasUrls():
            event.ignore()
            return

        valid_paths: list[Path] = []
        for url in mime.urls():
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() in _ACCEPTED_SUFFIXES:
                valid_paths.append(path)

        if valid_paths:
            event.acceptProposedAction()
            self.files_dropped.emit(valid_paths)
        else:
            event.ignore()

    def _reset_drop_state(self) -> None:
        self.setProperty("dragActive", False)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self._set_icon(DROP_ICON)
        self._main_label.setText(tr("drop.hint"))

    # ── File Picker ──────────────────────────────────────────────

    def _on_pick_file(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("drop.file_dialog_title"),
            str(Path.home()),
            tr("drop.file_filter"),
        )
        valid: list[Path] = []
        for fp in file_paths:
            path = Path(fp)
            if path.suffix.lower() in _ACCEPTED_SUFFIXES:
                valid.append(path)
        if valid:
            self.files_dropped.emit(valid)

    # ── Public methods ───────────────────────────────────────────

    def set_processing(self, processing: bool) -> None:
        """Disable drop zone while processing."""
        self.setAcceptDrops(not processing)
        self._pick_btn.setEnabled(not processing)
        if processing:
            self._main_label.setText(tr("drop.processing"))
            self._pick_btn.setText(tr("drop.processing_btn"))
        else:
            self._main_label.setText(tr("drop.hint"))
            self._pick_btn.setText(tr("drop.pick_multi"))

    def set_file_info(self, name: str, pkg_type: str) -> None:
        """Show selected file info."""
        self._main_label.setText(f"📦 {name}")
        self._sub_label.setText(tr("drop.file_type", type=pkg_type))

    def set_queue_info(self, count: int) -> None:
        """Show multi-file queue info."""
        self._main_label.setText(tr("drop.selected_count", count=count))
        self._sub_label.setText("")

    def retranslate(self) -> None:
        """Update all strings after language change."""
        self._main_label.setText(tr("drop.hint"))
        self._sub_label.setText(tr("drop.or"))
        self._pick_btn.setText(tr("drop.pick_multi"))
