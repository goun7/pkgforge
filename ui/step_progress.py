"""PkgForge — Step progress indicator widget.

Shows a horizontal step-by-step progress bar with animated
status indicators for each pipeline stage.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from i18n import tr
from ui.styles import Colors

# Step keys for i18n
_STEP_KEYS = [
    "step.security",
    "step.malware",
    "step.analysis",
    "step.conversion",
    "step.compatibility",
    "step.install",
]


class StepDot(QWidget):
    """Animated status dot for a pipeline step."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self._status = "pending"
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)
        self._pulse_phase = 0.0
        self._pulse_opacity = 0.0

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        self._status = value
        if value == "running":
            self._pulse_timer.start(30)
        else:
            self._pulse_timer.stop()
            self._pulse_opacity = 0.0
        self.update()

    def _pulse_tick(self) -> None:
        self._pulse_phase += 0.08
        self._pulse_opacity = 0.3 + 0.3 * math.sin(self._pulse_phase)
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2
        r = 10

        color_map = {
            "pending": QColor("#555"),
            "running": QColor(Colors.BLUE),
            "done": QColor(Colors.TEAL),
            "skipped": QColor("#5aa89a"),
            "warning": QColor(Colors.ORANGE),
            "error": QColor(Colors.RED),
        }
        color = color_map.get(self._status, QColor("#555"))

        if self._status == "running":
            glow = QColor(color)
            glow.setAlphaF(self._pulse_opacity)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - r - 3), int(cy - r - 3), int((r + 3) * 2), int((r + 3) * 2))

        if self._status == "pending":
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))

        painter.drawEllipse(int(cx - r), int(cy - r), r * 2, r * 2)

        if self._status in ("done", "skipped"):
            painter.setPen(QPen(Qt.GlobalColor.white, 2, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(int(cx - 4), int(cy), int(cx - 1), int(cy + 3))
            painter.drawLine(int(cx - 1), int(cy + 3), int(cx + 4), int(cy - 3))
        elif self._status == "error":
            painter.setPen(QPen(Qt.GlobalColor.white, 2, cap=Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(cx - 3), int(cy - 3), int(cx + 3), int(cy + 3))
            painter.drawLine(int(cx + 3), int(cy - 3), int(cx - 3), int(cy + 3))
        elif self._status == "warning":
            painter.setPen(QPen(Qt.GlobalColor.white, 2, cap=Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(cx), int(cy - 4), int(cx), int(cy + 1))
            painter.setBrush(QBrush(Qt.GlobalColor.white))
            painter.drawEllipse(int(cx - 1), int(cy + 3), 3, 3)
        elif self._status == "running":
            for i in range(3):
                angle = self._pulse_phase * 2 + i * (2 * math.pi / 3)
                dx = int(cx + 4 * math.cos(angle))
                dy = int(cy + 4 * math.sin(angle))
                painter.setBrush(QBrush(Qt.GlobalColor.white))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(dx - 1, dy - 1, 3, 3)

        painter.end()


class StepConnector(QWidget):
    """Connecting line between step dots."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setMinimumWidth(20)
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        self._active = value
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = self.height() // 2
        color = QColor(Colors.TEAL) if self._active else QColor("#444")
        painter.setPen(QPen(color, 2))
        painter.drawLine(0, y, self.width(), y)
        painter.end()


class StepProgress(QWidget):
    """Horizontal step progress indicator with i18n support."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("stepContainer")
        self._steps: dict[int, tuple[StepDot, QLabel]] = {}
        self._connectors: list[StepConnector] = []
        self._progress_bar = QProgressBar()
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)

        steps_layout = QHBoxLayout()
        steps_layout.setSpacing(0)

        for i, key in enumerate(_STEP_KEYS):
            step_col = QVBoxLayout()
            step_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_col.setSpacing(4)

            dot = StepDot()
            step_col.addWidget(dot, alignment=Qt.AlignmentFlag.AlignCenter)

            label = QLabel(tr(key))
            label.setObjectName("stepLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(80)
            step_col.addWidget(label)

            self._steps[i] = (dot, label)
            steps_layout.addLayout(step_col)

            if i < len(_STEP_KEYS) - 1:
                conn = StepConnector()
                self._connectors.append(conn)
                steps_layout.addWidget(conn)

        main_layout.addLayout(steps_layout)

        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        main_layout.addWidget(self._progress_bar)

    def set_step_status(self, step_index: int, status: str) -> None:
        if step_index not in self._steps:
            return
        dot, label = self._steps[step_index]
        dot.status = status
        label.setObjectName("stepLabelActive" if status == "running" else "stepLabel")
        style = label.style()
        if style is not None:
            style.unpolish(label)
            style.polish(label)
        for i, conn in enumerate(self._connectors):
            conn.active = i < step_index or (i == step_index and status in ("done", "warning", "skipped"))

    def set_progress(self, value: int) -> None:
        self._progress_bar.setValue(min(100, max(0, value)))

    def reset(self) -> None:
        for step_idx in self._steps:
            dot, label = self._steps[step_idx]
            dot.status = "pending"
            label.setObjectName("stepLabel")
            style = label.style()
            if style is not None:
                style.unpolish(label)
                style.polish(label)
        for conn in self._connectors:
            conn.active = False
        self._progress_bar.setValue(0)

    def retranslate(self) -> None:
        for i, key in enumerate(_STEP_KEYS):
            if i in self._steps:
                _, label = self._steps[i]
                label.setText(tr(key))