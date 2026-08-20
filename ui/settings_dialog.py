"""PkgForge — Settings dialog.

Provides UI for language, theme, AUR check, and distrobox preferences.
Settings are persisted to ~/.config/pkgforge/settings.json.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from i18n import tr, available_languages, get_language, load_setting, save_settings, load_settings
from config import discover_tools
from core.plugins import list_plugins, reload_plugins


class SettingsDialog(QDialog):
    """Application settings dialog.

    Signals:
        settings_changed(dict) – emitted when user saves, with full settings dict.
    """

    settings_changed = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumWidth(460)
        self.setMaximumWidth(560)
        self._setup_ui()
        self._load_current()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # ── Language ─────────────────────────────────────────────
        lang_group = QGroupBox(tr("settings.language"))
        lang_layout = QVBoxLayout(lang_group)

        self._lang_combo = QComboBox()
        for code, name in available_languages():
            self._lang_combo.addItem(name, code)
        lang_layout.addWidget(self._lang_combo)

        layout.addWidget(lang_group)

        # ── Theme ────────────────────────────────────────────────
        theme_group = QGroupBox(tr("settings.theme"))
        theme_layout = QVBoxLayout(theme_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItem(tr("settings.theme_dark"), "dark")
        self._theme_combo.addItem(tr("settings.theme_light"), "light")
        self._theme_combo.addItem(tr("settings.theme_system"), "system")
        theme_layout.addWidget(self._theme_combo)

        layout.addWidget(theme_group)

        # ── Features ─────────────────────────────────────────────
        features_group = QGroupBox("✨ " + tr("settings.title"))
        features_layout = QVBoxLayout(features_group)

        # AUR check
        self._aur_check = QCheckBox(tr("settings.aur_check"))
        self._aur_check.setToolTip(tr("settings.aur_check_desc"))
        features_layout.addWidget(self._aur_check)

        tools = discover_tools()
        self._distrobox_check = QCheckBox(tr("settings.distrobox"))
        if not tools.has_distrobox:
            self._distrobox_check.setToolTip(tr("settings.distrobox_desc") + tr("settings.distrobox_missing"))
        else:
            self._distrobox_check.setToolTip(tr("settings.distrobox_desc"))
        features_layout.addWidget(self._distrobox_check)

        # ClamAV malware scan
        self._clamav_check = QCheckBox(tr("settings.clamav_scan"))
        self._clamav_check.setToolTip(tr("settings.clamav_scan_desc"))
        features_layout.addWidget(self._clamav_check)

        # Snapshot before install
        self._snapshot_check = QCheckBox(tr("settings.snapshot"))
        self._snapshot_check.setToolTip(tr("settings.snapshot_desc"))
        features_layout.addWidget(self._snapshot_check)

        # Dry-run: convert + analyze only, never install
        self._dry_run_check = QCheckBox(tr("settings.dry_run"))
        self._dry_run_check.setToolTip(tr("settings.dry_run_desc"))
        features_layout.addWidget(self._dry_run_check)

        # Allow insecure http downloads (off = HTTPS only, recommended)
        self._insecure_http_check = QCheckBox(tr("settings.insecure_http"))
        self._insecure_http_check.setToolTip(tr("settings.insecure_http_desc"))
        features_layout.addWidget(self._insecure_http_check)

        layout.addWidget(features_group)

        # ── Plugins ─────────────────────────────────────────────
        plugins_group = QGroupBox("🔌 " + tr("settings.plugins"))
        plugins_layout = QVBoxLayout(plugins_group)

        self._plugin_checks: dict[str, QCheckBox] = {}
        plugins = list_plugins()
        if plugins:
            for p in plugins:
                cb = QCheckBox(f"{p['name']} ({', '.join(p['extensions'])})")
                cb.setToolTip(f"Öncelik: {p['priority']} — Sınıf: {p['class']}")
                cb.setChecked(load_setting(f"plugin_{p['name']}", True))
                self._plugin_checks[p['name']] = cb
                plugins_layout.addWidget(cb)

            # Reload button
            reload_btn = QPushButton(tr("settings.plugins_reload"))
            reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reload_btn.clicked.connect(self._reload_plugins)
            plugins_layout.addWidget(reload_btn)
        else:
            no_plugins = QLabel(tr("settings.plugins_none"))
            no_plugins.setStyleSheet("font-size: 11px; color: #888;")
            plugins_layout.addWidget(no_plugins)

        layout.addWidget(plugins_group)

        # ── Note ─────────────────────────────────────────────────
        note = QLabel(f"ℹ️ {tr('settings.restart_note')}")
        note.setStyleSheet("font-size: 11px; color: #888; padding: 4px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        # ── Buttons ──────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(tr("settings.cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(tr("settings.save"))
        save_btn.setObjectName("primaryBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _load_current(self) -> None:
        """Load current settings into UI."""
        # Language
        current_lang = get_language()
        idx = self._lang_combo.findData(current_lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)

        # Theme
        current_theme = load_setting("theme", "dark")
        idx = self._theme_combo.findData(current_theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)

        # Features
        self._aur_check.setChecked(load_setting("aur_check", True))
        self._distrobox_check.setChecked(load_setting("distrobox_fallback", False))
        self._clamav_check.setChecked(load_setting("clamav_scan", True))
        self._snapshot_check.setChecked(load_setting("snapshot", True))
        self._dry_run_check.setChecked(load_setting("dry_run", False))
        self._insecure_http_check.setChecked(load_setting("allow_insecure_http", False))

    def _save(self) -> None:
        """Save settings and emit signal."""
        settings = load_settings()
        settings["language"] = self._lang_combo.currentData()
        settings["theme"] = self._theme_combo.currentData()
        settings["aur_check"] = self._aur_check.isChecked()
        settings["distrobox_fallback"] = self._distrobox_check.isChecked()
        settings["clamav_scan"] = self._clamav_check.isChecked()
        settings["snapshot"] = self._snapshot_check.isChecked()
        settings["dry_run"] = self._dry_run_check.isChecked()
        settings["allow_insecure_http"] = self._insecure_http_check.isChecked()
        # Plugin enabled/disabled state
        for name, cb in self._plugin_checks.items():
            settings[f"plugin_{name}"] = cb.isChecked()
        save_settings(settings)
        self.settings_changed.emit(settings)
        self.accept()

    def _reload_plugins(self) -> None:
        """Hot-reload all plugins and refresh the UI."""
        reloaded = reload_plugins()
        # Update checkbox states
        for name, cb in self._plugin_checks.items():
            enabled = name in reloaded
            cb.setChecked(enabled)
            cb.setEnabled(True)
        # Show feedback
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            tr("settings.plugins"),
            tr("settings.plugins_reloaded").format(count=len(reloaded)),
        )
