"""PkgForge — Inline SVG icons.

All icons are stored as Python strings — no external file dependencies.
"""

from __future__ import annotations

# ── Application icon ─────────────────────────────────────────────

APP_ICON = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g1" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0dbc79"/>
      <stop offset="100%" stop-color="#0a8f5c"/>
    </linearGradient>
  </defs>
  <rect rx="12" width="64" height="64" fill="url(#g1)"/>
  <path d="M32 12 L18 42 H26 L28 36 H36 L38 42 H46 Z M30 30 L32 20 L34 30 Z"
        fill="white" opacity="0.95"/>
  <path d="M20 48 H44" stroke="white" stroke-width="2.5" stroke-linecap="round" opacity="0.7"/>
  <path d="M24 52 H40" stroke="white" stroke-width="2" stroke-linecap="round" opacity="0.5"/>
</svg>
"""

# ── File type icons ──────────────────────────────────────────────

DEB_ICON = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <rect rx="6" width="48" height="48" fill="#c62828"/>
  <text x="24" y="22" text-anchor="middle" fill="white"
        font-family="monospace" font-weight="bold" font-size="9">.deb</text>
  <rect x="10" y="28" width="28" height="3" rx="1.5" fill="white" opacity="0.3"/>
  <rect x="10" y="33" width="20" height="3" rx="1.5" fill="white" opacity="0.2"/>
</svg>
"""

RPM_ICON = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <rect rx="6" width="48" height="48" fill="#1565c0"/>
  <text x="24" y="22" text-anchor="middle" fill="white"
        font-family="monospace" font-weight="bold" font-size="9">.rpm</text>
  <rect x="10" y="28" width="28" height="3" rx="1.5" fill="white" opacity="0.3"/>
  <rect x="10" y="33" width="20" height="3" rx="1.5" fill="white" opacity="0.2"/>
</svg>
"""

PKG_ICON = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <rect rx="6" width="48" height="48" fill="#0dbc79"/>
  <text x="24" y="22" text-anchor="middle" fill="white"
        font-family="monospace" font-weight="bold" font-size="8">.pkg</text>
  <rect x="10" y="28" width="28" height="3" rx="1.5" fill="white" opacity="0.3"/>
  <rect x="10" y="33" width="20" height="3" rx="1.5" fill="white" opacity="0.2"/>
</svg>
"""

# ── Step status icons ────────────────────────────────────────────

ICON_PENDING = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" fill="none" stroke="#666" stroke-width="2"/>
</svg>
"""

ICON_RUNNING = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" fill="none" stroke="#2196f3" stroke-width="2"
          stroke-dasharray="20 40" stroke-linecap="round">
    <animateTransform attributeName="transform" type="rotate"
                      values="0 12 12;360 12 12" dur="1s" repeatCount="indefinite"/>
  </circle>
</svg>
"""

ICON_SUCCESS = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" fill="#0dbc79"/>
  <path d="M8 12 L11 15 L16 9" fill="none" stroke="white" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

ICON_WARNING = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" fill="#ff9800"/>
  <path d="M12 8 V14" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="12" cy="17" r="1.2" fill="white"/>
</svg>
"""

ICON_ERROR = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" fill="#f44336"/>
  <path d="M8 8 L16 16 M16 8 L8 16" stroke="white" stroke-width="2.5"
        stroke-linecap="round"/>
</svg>
"""

# ── Drop zone icons ──────────────────────────────────────────────

DROP_ICON = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="4" y="4" width="56" height="56" rx="12" fill="none"
        stroke="#555" stroke-width="2" stroke-dasharray="8 4"/>
  <path d="M32 18 V38 M24 30 L32 38 L40 30" fill="none"
        stroke="#888" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="16" y="42" width="32" height="4" rx="2" fill="#888" opacity="0.3"/>
</svg>
"""

DROP_ICON_ACTIVE = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="4" y="4" width="56" height="56" rx="12" fill="none"
        stroke="#0dbc79" stroke-width="3" stroke-dasharray="8 4">
    <animate attributeName="stroke-dashoffset" values="0;-24" dur="1s" repeatCount="indefinite"/>
  </rect>
  <path d="M32 18 V38 M24 30 L32 38 L40 30" fill="none"
        stroke="#0dbc79" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="16" y="42" width="32" height="4" rx="2" fill="#0dbc79" opacity="0.3"/>
</svg>
"""

# ── Log level icons ──────────────────────────────────────────────

ICON_LOG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
  <rect x="2" y="3" width="16" height="14" rx="2" fill="none" stroke="#888" stroke-width="1.5"/>
  <line x1="5" y1="7" x2="15" y2="7" stroke="#888" stroke-width="1"/>
  <line x1="5" y1="10" x2="13" y2="10" stroke="#888" stroke-width="1"/>
  <line x1="5" y1="13" x2="11" y2="13" stroke="#888" stroke-width="1"/>
</svg>
"""

ICON_SECURITY = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path d="M12 2 L4 6 V12 C4 17 8 21 12 22 C16 21 20 17 20 12 V6 Z"
        fill="none" stroke="#0dbc79" stroke-width="2"/>
  <path d="M9 12 L11 14 L15 10" fill="none" stroke="#0dbc79"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

# ── Header toolbar icons ─────────────────────────────────
# The stroke color is injected at render time via ``.format(color=...)`` so the
# icons follow the active theme's accent (matching the header text color).

HEADER_URL = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
     stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="9"/>
  <path d="M3 12 H21"/>
  <path d="M12 3 C15 6 15 18 12 21 C9 18 9 6 12 3 Z"/>
</svg>
"""

HEADER_HISTORY = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
     stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="5" y="4" width="14" height="17" rx="2"/>
  <path d="M9 4 V3 H15 V4"/>
  <path d="M8 9 H16 M8 13 H16 M8 17 H13"/>
</svg>
"""

HEADER_UPDATES = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
     stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="18" r="2"/>
  <path d="M8 14 A5 5 0 0 1 16 14"/>
  <path d="M5 11 A9 9 0 0 1 19 11"/>
</svg>
"""

HEADER_SETTINGS = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
     stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M4 8 H20 M4 16 H20"/>
  <circle cx="9" cy="8" r="2.6" fill="{color}" stroke="none"/>
  <circle cx="15" cy="16" r="2.6" fill="{color}" stroke="none"/>
</svg>
"""

HEADER_ABOUT = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
     stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="9"/>
  <path d="M12 11 V16"/>
  <path d="M12 8 H12.01"/>
</svg>
"""

HEADER_TOOLS = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
     stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
</svg>
"""
