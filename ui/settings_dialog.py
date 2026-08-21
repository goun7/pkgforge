"""PkgForge — Settings dialog.

Provides UI for language, theme, AUR check, distrobox preferences, and advanced settings.
Settings are persisted to ~/.config/pkgforge/settings.json.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import discover_tools
from core.plugins import list_plugins, reload_plugins
from i18n import (
    available_languages,
    get_language,
    load_setting,
    load_settings,
    save_settings,
    tr,
)


class SettingsDialog(QDialog):
    """Application settings dialog.

    Signals:
        settings_changed(dict) – emitted when user saves, with full settings dict.
    """

    settings_changed = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumWidth(500)
        self.setMaximumWidth(620)
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

        # ── Advanced Settings ────────────────────────────────────
        advanced_group = QGroupBox("🔧 " + tr("settings.advanced"))
        advanced_layout = QVBoxLayout(advanced_group)

        # Timeout
        timeout_row = QHBoxLayout()
        timeout_label = QLabel(tr("settings.timeout"))
        timeout_label.setToolTip(tr("settings.timeout_desc"))
        timeout_row.addWidget(timeout_label)
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(10, 600)
        self._timeout_spin.setSuffix(" s")
        self._timeout_spin.setToolTip(tr("settings.timeout_desc"))
        timeout_row.addWidget(self._timeout_spin)
        timeout_row.addStretch()
        advanced_layout.addLayout(timeout_row)

        # Default output directory
        outdir_row = QHBoxLayout()
        outdir_label = QLabel(tr("settings.output_dir"))
        outdir_label.setToolTip(tr("settings.output_dir_desc"))
        outdir_row.addWidget(outdir_label)
        self._outdir_input = QLineEdit()
        self._outdir_input.setPlaceholderText(tr("settings.output_dir_placeholder"))
        self._outdir_input.setReadOnly(True)
        outdir_row.addWidget(self._outdir_input, stretch=1)
        outdir_browse = QPushButton("📂")
        outdir_browse.setFixedWidth(36)
        outdir_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        outdir_browse.clicked.connect(self._browse_output_dir)
        outdir_row.addWidget(outdir_browse)
        advanced_layout.addLayout(outdir_row)

        # Verbose mode
        self._verbose_check = QCheckBox(tr("settings.verbose"))
        self._verbose_check.setToolTip(tr("settings.verbose_desc"))
        advanced_layout.addWidget(self._verbose_check)

        # Auto-sign
        self._auto_sign_check = QCheckBox(tr("settings.auto_sign"))
        self._auto_sign_check.setToolTip(tr("settings.auto_sign_desc"))
        advanced_layout.addWidget(self._auto_sign_check)

        layout.addWidget(advanced_group)

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

        # ── Live Config Preview ──────────────────────────────────
        preview_group = QGroupBox("👁️ Canlı Önizleme")
        preview_layout = QVBoxLayout(preview_group)

        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setMaximumHeight(140)
        self._preview_text.setStyleSheet(
            "QTextEdit { background: #1a1a2e; color: #00ff88; font-family: monospace; "
            "font-size: 11px; border: 1px solid #333; border-radius: 4px; padding: 8px; }"
        )
        preview_layout.addWidget(self._preview_text)

        # Connect all inputs to live preview
        self._lang_combo.currentIndexChanged.connect(self._update_preview)
        self._theme_combo.currentIndexChanged.connect(self._update_preview)
        self._aur_check.toggled.connect(self._update_preview)
        self._distrobox_check.toggled.connect(self._update_preview)
        self._clamav_check.toggled.connect(self._update_preview)
        self._snapshot_check.toggled.connect(self._update_preview)
        self._dry_run_check.toggled.connect(self._update_preview)
        self._insecure_http_check.toggled.connect(self._update_preview)
        self._timeout_spin.valueChanged.connect(self._update_preview)
        self._verbose_check.toggled.connect(self._update_preview)
        self._auto_sign_check.toggled.connect(self._update_preview)

        layout.addWidget(preview_group)

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

        # Advanced
        self._timeout_spin.setValue(load_setting("timeout_seconds", 120))
        self._outdir_input.setText(load_setting("output_dir", ""))
        self._verbose_check.setChecked(load_setting("verbose", False))
        self._auto_sign_check.setChecked(load_setting("auto_sign", False))

        # Initial preview
        self._update_preview()

    def _update_preview(self) -> None:
        """Update the live JSON preview panel with current UI state."""
        config = {
            "language": self._lang_combo.currentData(),
            "theme": self._theme_combo.currentData(),
            "aur_check": self._aur_check.isChecked(),
            "distrobox_fallback": self._distrobox_check.isChecked(),
            "clamav_scan": self._clamav_check.isChecked(),
            "snapshot": self._snapshot_check.isChecked(),
            "dry_run": self._dry_run_check.isChecked(),
            "allow_insecure_http": self._insecure_http_check.isChecked(),
            "timeout_seconds": self._timeout_spin.value(),
            "output_dir": self._outdir_input.text() or None,
            "verbose": self._verbose_check.isChecked(),
            "auto_sign": self._auto_sign_check.isChecked(),
        }
        self._preview_text.setPlainText(json.dumps(config, indent=2, ensure_ascii=False))

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
        # Advanced
        settings["timeout_seconds"] = self._timeout_spin.value()
        settings["output_dir"] = self._outdir_input.text()
        settings["verbose"] = self._verbose_check.isChecked()
        settings["auto_sign"] = self._auto_sign_check.isChecked()
        # Plugin enabled/disabled state
        for name, cb in self._plugin_checks.items():
            settings[f"plugin_{name}"] = cb.isChecked()
        save_settings(settings)
        self.settings_changed.emit(settings)
        self.accept()

    def _browse_output_dir(self) -> None:
        """Open folder chooser for default output directory."""
        current = self._outdir_input.text() or ""
        directory = QFileDialog.getExistingDirectory(self, tr("settings.output_dir"), current)
        if directory:
            self._outdir_input.setText(directory)

    def _reload_plugins(self) -> None:
        """Hot-reload all plugins and refresh the UI."""
        reloaded = reload_plugins()
        for name, cb in self._plugin_checks.items():
            enabled = name in reloaded
            cb.setChecked(enabled)
            cb.setEnabled(True)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            tr("settings.plugins"),
            tr("settings.plugins_reloaded").format(count=len(reloaded)),
        )
