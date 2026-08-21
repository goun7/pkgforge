"""PkgForge — Styles and theming.

Three theme modes:
- System: Follow KDE/Qt palette (auto-detect dark/light)
- PkgForge Dark: Deep navy + neon teal accents
- PkgForge Light: Clean white + dark teal accents
"""

from __future__ import annotations

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

from i18n import load_setting

# ── Color Palettes ──────────────────────────────────────────────

class Colors:
    """Application color constants (defaults to PkgForge Dark)."""
    TEAL = "#00f5a0"
    TEAL_DARK = "#00c97d"
    TEAL_LIGHT = "#4dffc3"
    TEAL_HOVER = "#33f7b0"

    RED = "#ff4757"
    RED_DARK = "#e63946"
    ORANGE = "#ffa502"
    ORANGE_DARK = "#e09400"
    BLUE = "#3742fa"
    BLUE_DARK = "#2e36d4"

    SURFACE = "#0a0e1a"
    SURFACE_ALT = "#121829"
    SURFACE_HOVER = "#1a2038"
    SURFACE_CARD = "rgba(18, 24, 41, 0.95)"
    BORDER = "rgba(0, 245, 160, 0.12)"
    BORDER_HOVER = "rgba(0, 245, 160, 0.25)"
    TEXT = "#e8ecf4"
    TEXT_DIM = "#8b95a8"
    TEXT_MUTED = "#5a6478"

    # Neon glow
    GLOW = "rgba(0, 245, 160, 0.15)"
    GLOW_STRONG = "rgba(0, 245, 160, 0.25)"


class LightColors(Colors):
    """Light theme overrides."""
    TEAL = "#047857"
    TEAL_DARK = "#065f46"
    TEAL_LIGHT = "#10b981"
    TEAL_HOVER = "#059669"

    SURFACE = "#fafbfc"
    SURFACE_ALT = "#ffffff"
    SURFACE_HOVER = "#f0f1f3"
    SURFACE_CARD = "rgba(255, 255, 255, 0.98)"
    BORDER = "rgba(0, 0, 0, 0.08)"
    BORDER_HOVER = "rgba(4, 120, 87, 0.2)"
    TEXT = "#111827"
    TEXT_DIM = "#6b7280"
    TEXT_MUTED = "#9ca3af"
    GLOW = "rgba(4, 120, 87, 0.06)"
    GLOW_STRONG = "rgba(4, 120, 87, 0.12)"


class SystemDarkColors(Colors):
    """System dark theme (softer than PkgForge Dark)."""
    TEAL = "#0dbc79"
    TEAL_DARK = "#0a8f5c"
    TEAL_LIGHT = "#4dd8a5"
    TEAL_HOVER = "#0fd98d"

    SURFACE = "#1e1e2e"
    SURFACE_ALT = "#252535"
    SURFACE_HOVER = "#2a2a3e"
    SURFACE_CARD = "rgba(30, 30, 46, 0.85)"
    BORDER = "rgba(255, 255, 255, 0.08)"
    BORDER_HOVER = "rgba(13, 188, 121, 0.2)"
    TEXT = "#e0e0e0"
    TEXT_DIM = "#888"
    TEXT_MUTED = "#666"
    GLOW = "rgba(13, 188, 121, 0.08)"
    GLOW_STRONG = "rgba(13, 188, 121, 0.15)"


class SystemLightColors(Colors):
    """System light theme."""
    TEAL = "#0dbc79"
    TEAL_DARK = "#0a8f5c"
    TEAL_LIGHT = "#4dd8a5"
    TEAL_HOVER = "#0fd98d"

    SURFACE = "#f5f5f5"
    SURFACE_ALT = "#ffffff"
    SURFACE_HOVER = "#e8e8e8"
    SURFACE_CARD = "rgba(255, 255, 255, 0.9)"
    BORDER = "rgba(0, 0, 0, 0.08)"
    BORDER_HOVER = "rgba(13, 188, 121, 0.2)"
    TEXT = "#1a1a1a"
    TEXT_DIM = "#555"
    TEXT_MUTED = "#888"
    GLOW = "rgba(13, 188, 121, 0.05)"
    GLOW_STRONG = "rgba(13, 188, 121, 0.1)"


def is_dark_theme() -> bool:
    """Detect if the current system theme is dark."""
    app = QApplication.instance()
    if app is None:
        return True
    palette = app.palette()
    bg = palette.color(QPalette.ColorRole.Window)
    return bg.lightness() < 128


def get_theme_name() -> str:
    """Get the active theme name from settings."""
    return load_setting("theme", "dark")


def get_colors(theme: str | None = None) -> Colors:
    """Get color palette for the specified or active theme."""
    if theme is None:
        theme = get_theme_name()

    if theme == "dark":
        return Colors()  # PkgForge Dark
    elif theme == "light":
        return LightColors()
    elif theme == "system":
        return SystemDarkColors() if is_dark_theme() else SystemLightColors()
    else:
        return Colors()


# ── Stylesheet generator ────────────────────────────────────────

def build_stylesheet(theme: str | None = None) -> str:
    """Build the complete application stylesheet."""
    c = get_colors(theme)
    is_dark = not isinstance(c, (LightColors, SystemLightColors))

    # Header styling for dark/light contrast
    header_grad = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e293b)" if is_dark else "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f8fafc, stop:1 #e2e8f0)"

    return f"""
    /* ── Global ───────────────────────────────────────── */
    QMainWindow {{
        background-color: {c.SURFACE};
    }}

    QWidget {{
        color: {c.TEXT};
        font-family: "Inter", "Noto Sans", "Segoe UI", system-ui, sans-serif;
        font-size: 13px;
    }}

    /* ── Header Bar ───────────────────────────────────── */
    #headerBar {{
        background: {header_grad};
        border-bottom: 2px solid {c.TEAL};
        min-height: 56px;
        padding: 0 16px;
    }}

    #headerTitle {{
        color: {c.TEAL};
        font-size: 20px;
        font-weight: 800;
        letter-spacing: 1px;
    }}

    #headerSubtitle {{
        color: {"#94a3b8" if is_dark else "#475569"};
        font-size: 12px;
        letter-spacing: 0.3px;
    }}

    QPushButton#headerBtn {{
        background-color: {"rgba(30, 41, 59, 0.8)" if is_dark else "#ffffff"};
        color: {c.TEAL};
        border: 1px solid {c.BORDER};
        border-radius: 10px;
        padding: 0px;
        font-size: 20px;
    }}

    QPushButton#headerBtn:hover {{
        background-color: {c.GLOW_STRONG};
        border-color: {c.TEAL};
    }}

    /* ── Drop Zone ────────────────────────────────────── */
    #dropZone {{
        background: {c.SURFACE_CARD};
        border: 2px dashed {c.BORDER};
        border-radius: 16px;
        min-height: 220px;
    }}

    #dropZone:hover {{
        border-color: {c.TEAL};
        background: {c.GLOW};
    }}

    #dropZone[dragActive="true"] {{
        border-color: {c.TEAL};
        border-style: solid;
        background: {c.GLOW_STRONG};
        border-width: 3px;
    }}

    #dropLabel {{
        color: {c.TEXT_DIM};
        font-size: 15px;
        font-weight: 500;
    }}

    #dropSubLabel {{
        color: {c.TEXT_MUTED};
        font-size: 12px;
    }}

    /* ── Buttons ──────────────────────────────────────── */
    QPushButton {{
        background-color: {c.SURFACE_ALT};
        border: 1px solid {c.BORDER};
        border-radius: 10px;
        padding: 10px 22px;
        font-weight: 600;
        min-height: 20px;
    }}

    QPushButton:hover {{
        background-color: {c.SURFACE_HOVER};
        border-color: {c.TEAL};
    }}

    QPushButton:pressed {{
        background-color: {c.TEAL_DARK};
        color: white;
    }}

    QPushButton#primaryBtn {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {c.TEAL_DARK}, stop:1 {c.TEAL}
        );
        color: {"#0a0e1a" if is_dark else "white"};
        border: none;
        font-weight: 700;
    }}

    QPushButton#primaryBtn:hover {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {c.TEAL}, stop:1 {c.TEAL_HOVER}
        );
    }}

    QPushButton#primaryBtn:disabled {{
        background: {c.SURFACE_ALT};
        color: {c.TEXT_MUTED};
    }}

    QPushButton#dangerBtn {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c.RED_DARK}, stop:1 {c.RED});
        color: white;
        border: none;
    }}

    QPushButton#dangerBtn:hover {{
        background: {c.RED};
    }}

    /* ── Step Progress ────────────────────────────────── */
    #stepContainer {{
        background: {c.SURFACE_CARD};
        border: 1px solid {c.BORDER};
        border-radius: 14px;
        padding: 16px;
    }}

    #stepLabel {{
        font-size: 11px;
        font-weight: 600;
        color: {c.TEXT_DIM};
    }}

    #stepLabelActive {{
        color: {c.TEAL};
        font-weight: 700;
        font-size: 11px;
    }}

    QProgressBar {{
        background-color: {c.SURFACE_ALT};
        border: none;
        border-radius: 5px;
        min-height: 10px;
        max-height: 10px;
    }}

    QProgressBar::chunk {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {c.TEAL_DARK}, stop:0.5 {c.TEAL}, stop:1 {"#00d4ff" if is_dark else c.TEAL_DARK}
        );
        border-radius: 5px;
    }}

    /* ── Log Panel ────────────────────────────────────── */
    #logPanel {{
        background: {"#060a14" if is_dark else "#fafafa"};
        border: 1px solid {c.BORDER};
        border-radius: 10px;
    }}

    #logText {{
        background: transparent;
        border: none;
        font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
        font-size: 12px;
        padding: 8px;
        selection-background-color: {c.TEAL_DARK};
    }}

    #logToggle {{
        background: transparent;
        border: none;
        color: {c.TEXT_DIM};
        font-size: 12px;
        padding: 4px 8px;
    }}

    #logToggle:hover {{
        color: {c.TEAL};
    }}

    /* ── Result Dialog ────────────────────────────────── */
    QDialog {{
        background-color: {c.SURFACE};
    }}

    #resultTitle {{
        font-size: 18px;
        font-weight: 700;
    }}

    /* ── Info & Queue Cards ───────────────────────────── */
    #infoCard {{
        background: {c.SURFACE_ALT};
        border: 1px solid {c.BORDER};
        border-radius: 12px;
        padding: 14px 18px;
    }}

    #infoLabel {{
        color: {c.TEXT_DIM};
        font-size: 11px;
    }}

    #infoValue {{
        font-weight: 600;
        font-size: 13px;
    }}

    #queueItem {{
        background: {c.SURFACE_ALT};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        padding: 6px 10px;
    }}

    #queueItem:hover {{
        border-color: {c.TEAL};
    }}

    #queueItemActive {{
        background: {c.GLOW};
        border: 1px solid {c.TEAL};
        border-radius: 8px;
        padding: 6px 10px;
    }}

    /* ── Settings Dialog ──────────────────────────────── */
    QComboBox {{
        background-color: {c.SURFACE_ALT};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        padding: 6px 12px;
        min-height: 24px;
    }}

    QComboBox:hover {{
        border-color: {c.TEAL};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {c.SURFACE_ALT};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        selection-background-color: {c.TEAL_DARK};
        padding: 4px;
    }}

    QCheckBox {{
        spacing: 8px;
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 2px solid {c.BORDER};
        background: {c.SURFACE_ALT};
    }}

    QCheckBox::indicator:checked {{
        background: {c.TEAL};
        border-color: {c.TEAL};
    }}

    QGroupBox {{
        border: 1px solid {c.BORDER};
        border-radius: 10px;
        margin-top: 12px;
        padding-top: 20px;
        font-weight: 600;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        color: {c.TEAL};
    }}

    /* ── Scrollbar ────────────────────────────────────── */
    QScrollArea {{
        background: transparent;
        border: none;
    }}

    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: {c.TEXT_MUTED};
        border-radius: 4px;
        min-height: 40px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {c.TEAL};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    /* ── Tooltips ─────────────────────────────────────── */
    QToolTip {{
        background: {c.SURFACE_ALT};
        color: {c.TEXT};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 12px;
    }}

    /* ── Status Bar ───────────────────────────────────── */
    QStatusBar {{
        background: {c.SURFACE};
        border-top: 1px solid {c.BORDER};
        font-size: 11px;
        padding: 2px 8px;
        color: {c.TEXT_DIM};
    }}
    """
