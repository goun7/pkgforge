"""PkgForge — Internationalization (i18n) system.

Provides TR/EN language switching with persistent settings.
All UI strings are accessed via the `tr()` function.
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from config import profile_config_dir, settings_file

log = logging.getLogger(__name__)

# Current language (module-level state)
_current_lang: str = "tr"
_strings: dict[str, str] = {}


def _load_language_module(lang: str) -> dict[str, str]:
    """Load string dictionary for a given language code."""
    if lang == "tr":
        from i18n.lang_tr import STRINGS
        return STRINGS
    elif lang == "en":
        from i18n.lang_en import STRINGS
        return STRINGS
    else:
        log.warning("Bilinmeyen dil: %s, Türkçe'ye dönülüyor", lang)
        from i18n.lang_tr import STRINGS
        return STRINGS


def init_language(lang: str | None = None) -> None:
    """Initialize the i18n system.

    If *lang* is None, reads from settings file or falls back to 'tr'.
    """
    global _current_lang, _strings

    if lang is None:
        lang = load_setting("language", "tr")

    _current_lang = lang
    _strings = _load_language_module(lang)
    log.info("Dil ayarlandı: %s (%d string)", lang, len(_strings))


def tr(key: str, **kwargs: Any) -> str:
    """Translate a string key to the current language.

    Supports {placeholder} formatting via kwargs.

    Example:
        tr("log.lines", count=42)  →  "42 satır"
    """
    if not _strings:
        init_language()

    text = _strings.get(key, "")
    if not text:
        # Fallback: try Turkish
        if _current_lang != "tr":
            from i18n.lang_tr import STRINGS as tr_strings
            text = tr_strings.get(key, key)
        else:
            text = key  # Return key itself as last resort

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return text


def set_language(lang: str) -> None:
    """Switch the active language and persist the choice."""
    global _current_lang, _strings
    _current_lang = lang
    _strings = _load_language_module(lang)
    save_setting("language", lang)


def get_language() -> str:
    """Return the current language code."""
    return _current_lang


def available_languages() -> list[tuple[str, str]]:
    """Return list of (code, display_name) tuples."""
    return [("tr", "Türkçe"), ("en", "English")]


# ── Settings persistence ─────────────────────────────────────────

def _ensure_config_dir() -> None:
    # Resolved per call so the active profile (C2) takes effect immediately.
    profile_config_dir().mkdir(parents=True, exist_ok=True)


def load_settings() -> dict[str, Any]:
    """Load all settings from the active profile."""
    path = settings_file()
    if path.is_file():
        try:
            return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Ayarlar okunamadı: %s", exc)
    return {}


def save_settings(settings: dict[str, Any]) -> None:
    """Save all settings to the active profile."""
    _ensure_config_dir()
    settings_file().write_text(
        json.dumps(settings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_setting(key: str, default: Any = None) -> Any:
    """Load a single setting."""
    return load_settings().get(key, default)


def save_setting(key: str, value: Any) -> None:
    """Save a single setting."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
