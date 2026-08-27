"""PkgForge — Fleet konsolu dialog'u (PyQt6, ikincil UI).

core.fleet.get_fleet_status() agregasyonunu tek ekranda gosterir:
backend durumu, politika seviyesi, profiller, gecmis/age/senkron ozeti.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from i18n import tr
from ui.background_worker import run_in_background


class FleetDialog(QDialog):
    """Fleet konsolu: tek-cagri fleet.status ozeti."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("fleet.title"))
        self.resize(560, 460)
        lay = QVBoxLayout(self)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        lay.addWidget(self._summary)

        self._detail = QLabel("")
        self._detail.setWordWrap(True)
        lay.addWidget(self._detail)

        self._refresh_btn = QPushButton(tr("fleet.refresh"))
        self._refresh_btn.clicked.connect(self._load)
        lay.addWidget(self._refresh_btn)
        lay.addStretch()

        self._load()

    def _load(self) -> None:
        from core.fleet import get_fleet_status
        self._summary.setText(tr("tools.running"))

        def _op():
            return get_fleet_status()

        def _done(res) -> None:
            self._render(res)

        def _err(msg: str) -> None:
            self._summary.setText(f"❌ {msg}")

        run_in_background(_op, _done, _err)

    def _render(self, res: dict) -> None:
        backends = res.get("backends", {})
        lines = []
        for name in res.get("backend_names", []):
            b = backends.get(name, {})
            avail = "✓" if b.get("available") else "✗"
            conf = f"  ({tr('fleet.configured')})" if b.get("configured") else ""
            lines.append(f"{avail} {name}{conf}")
        self._summary.setText("\n".join(lines))

        profiles = ", ".join(res.get("profiles", [])) or "-"
        age = tr("fleet.present") if res.get("age_available") else tr("fleet.absent")
        sync = (tr("fleet.configured") if res.get("sync_configured")
                else tr("fleet.absent"))
        detail = (
            f"{tr('fleet.policy')}: {res.get('policy_level', '?')}\n"
            f"{tr('fleet.profiles')}: {profiles}\n"
            f"{tr('fleet.history')}: {res.get('history_count', 0)}\n"
            f"age: {age}\n"
            f"{tr('fleet.sync')}: {sync}"
        )
        self._detail.setText(detail)
