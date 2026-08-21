"""PkgForge — Confirmation Dialog.

Reusable confirmation dialog for critical operations.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ui.styles import get_colors


class ConfirmDialog(QDialog):
    """Reusable confirmation dialog."""

    def __init__(
        self,
        title: str,
        message: str,
        confirm_text: str = "Onayla",
        cancel_text: str = "İptal",
        danger: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(f"font-size: 14px; color: {get_colors().TEXT};")
        layout.addWidget(msg_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(cancel_text)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton(confirm_text)
        if danger:
            confirm_btn.setStyleSheet(
                f"background-color: {get_colors().RED}; color: white; "
                f"padding: 8px 16px; border-radius: 4px;"
            )
        else:
            confirm_btn.setStyleSheet(
                f"background-color: {get_colors().TEAL}; color: #0a0e1a; "
                f"padding: 8px 16px; border-radius: 4px; font-weight: bold;"
            )
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)


def confirm_action(
    title: str,
    message: str,
    confirm_text: str = "Onayla",
    danger: bool = False,
    parent=None,
) -> bool:
    """Show a confirmation dialog and return True if confirmed.

    Args:
        title: Dialog title.
        message: Confirmation message.
        confirm_text: Text for the confirm button.
        danger: If True, use red confirm button.
        parent: Parent widget.

    Returns:
        True if user confirmed, False otherwise.
    """
    dialog = ConfirmDialog(
        title=title,
        message=message,
        confirm_text=confirm_text,
        danger=danger,
        parent=parent,
    )
    return dialog.exec() == QDialog.DialogCode.Accepted
