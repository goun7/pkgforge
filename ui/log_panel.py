"""PkgForge — Live log panel widget.

Collapsible panel that displays color-coded log messages
from the conversion pipeline in real-time.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from i18n import tr
from ui.styles import Colors

_LEVEL_STYLES: dict[str, tuple[str, str]] = {
    "info": (Colors.TEXT, ""),
    "success": (Colors.TEAL, "✓"),
    "warning": (Colors.ORANGE, "⚠"),
    "error": (Colors.RED, "✗"),
}


class LogPanel(QWidget):
    """Collapsible log panel with color-coded output."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("logPanel")
        self._expanded = False
        self._log_lines: list[tuple[str, str, str]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toggle_bar = QHBoxLayout()
        toggle_bar.setContentsMargins(8, 4, 8, 4)

        self._toggle_btn = QPushButton(tr("log.title_collapsed"))
        self._toggle_btn.setObjectName("logToggle")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        toggle_bar.addWidget(self._toggle_btn)

        toggle_bar.addStretch()

        self._count_label = QLabel(tr("log.lines", count=0))
        self._count_label.setObjectName("logToggle")
        toggle_bar.addWidget(self._count_label)

        self._export_btn = QPushButton("💾")
        self._export_btn.setObjectName("logToggle")
        self._export_btn.setToolTip(tr("log.export_title"))
        self._export_btn.setAccessibleName(tr("log.export_title"))
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.clicked.connect(self._export_log)
        self._export_btn.setFixedWidth(32)
        self._export_btn.setVisible(False)
        toggle_bar.addWidget(self._export_btn)

        layout.addLayout(toggle_bar)

        self._text_edit = QTextEdit()
        self._text_edit.setObjectName("logText")
        self._text_edit.setReadOnly(True)
        self._text_edit.setVisible(False)
        self._text_edit.setMinimumHeight(0)
        self._text_edit.setMaximumHeight(200)

        font = QFont("JetBrains Mono", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._text_edit.setFont(font)

        layout.addWidget(self._text_edit)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._text_edit.setVisible(self._expanded)
        self._export_btn.setVisible(self._expanded)
        self._toggle_btn.setText(
            tr("log.title_expanded") if self._expanded else tr("log.title_collapsed")
        )

    def append_log(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_lines.append((timestamp, level, message))

        color, prefix = _LEVEL_STYLES.get(level, (Colors.TEXT, ""))
        formatted = f'<span style="color:#666">{timestamp}</span> '
        if prefix:
            formatted += f'<span style="color:{color}">{prefix}</span> '
        formatted += f'<span style="color:{color}">{_escape_html(message)}</span>'

        self._text_edit.append(formatted)

        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text_edit.setTextCursor(cursor)

        self._count_label.setText(tr("log.lines", count=len(self._log_lines)))

        if level == "error" and not self._expanded:
            self._toggle()

    def clear(self) -> None:
        self._log_lines.clear()
        self._text_edit.clear()
        self._count_label.setText(tr("log.lines", count=0))

    def _export_log(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("log.export_title"),
            str(Path.home() / f"pkgforge_{datetime.now():%Y%m%d_%H%M%S}.log"),
            tr("log.export_filter"),
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(f"[{ts}] [{level.upper():7s}] {msg}\n" for ts, level, msg in self._log_lines)

    def retranslate(self) -> None:
        self._toggle_btn.setText(
            tr("log.title_expanded") if self._expanded else tr("log.title_collapsed")
        )
        self._count_label.setText(tr("log.lines", count=len(self._log_lines)))


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
