"""PkgForge — Loading Indicator Widget.

Shows a spinner animation and status text during long operations.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout

from i18n import tr
from ui.styles import get_colors


class SpinnerWidget(QWidget):
    """Animated spinner widget."""

    def __init__(self, size: int = 24, color: str | None = None, parent=None):
        super().__init__(parent)
        self._size = size
        self._color = color or get_colors().TEAL
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.setFixedSize(size, size)

    def _rotate(self):
        self._angle = (self._angle + 10) % 360
        self.update()

    def start(self):
        self._timer.start(50)
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(self._color))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        # Draw spinning arc
        x = (self._size - 20) // 2
        y = (self._size - 20) // 2
        painter.drawArc(x, y, 20, 20, self._angle * 16, 270 * 16)
        painter.end()


class LoadingIndicator(QWidget):
    """Composite loading indicator with spinner + text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._spinner = SpinnerWidget(size=20)
        layout.addWidget(self._spinner)

        self._label = QLabel("")
        self._label.setStyleSheet(f"color: {get_colors().TEXT_DIM}; font-size: 12px;")
        layout.addWidget(self._label)

        layout.addStretch()

    def start(self, text: str = ""):
        """Start the loading indicator with optional text."""
        self._label.setText(text)
        self._spinner.start()
        self.show()

    def stop(self):
        """Stop the loading indicator."""
        self._spinner.stop()
        self.hide()

    def update_text(self, text: str):
        """Update the status text."""
        self._label.setText(text)
