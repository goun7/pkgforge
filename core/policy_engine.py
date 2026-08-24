"""Faz 5 (F5.19) — politika motoru: profil bazli compat esikleri.

Uyumluluk raporunun hangi ciddiyet seviyesinde kurulumu bloklayacagini
profil/ayarlardan okunan bir politika belirler. Varsayilan 'standard' yalnizca
ERROR'da bloklar; 'strict' WARNING'de de bloklar. Motor saf ve test edilebilir;
rapor yoksa zarif duser.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from core.compatibility_checker import CheckSeverity

# Ciddiyet siralamasi (karsilastirma icin).
_ORDER = {
    CheckSeverity.PASS: 0,
    CheckSeverity.WARNING: 1,
    CheckSeverity.ERROR: 2,
}


class PolicyLevel(Enum):
    STANDARD = "standard"   # yalnizca ERROR bloklar
    STRICT = "strict"       # WARNING ve ERROR bloklar


# Her politika seviyesinin blokaj esigi.
_BLOCK_AT = {
    PolicyLevel.STANDARD: CheckSeverity.ERROR,
    PolicyLevel.STRICT: CheckSeverity.WARNING,
}

SETTINGS_KEY = "compat_policy"


def policy_from_settings(settings: dict | None = None) -> PolicyLevel:
    """Read the active policy level from settings (default: standard)."""
    if settings is None:
        import i18n

        settings = i18n.load_settings()
    raw = str(settings.get(SETTINGS_KEY, "standard")).lower().strip()
    try:
        return PolicyLevel(raw)
    except ValueError:
        return PolicyLevel.STANDARD


def evaluate(report: Any, level: PolicyLevel | None = None) -> dict[str, Any]:
    """Decide whether a compatibility report allows installation.

    *report* may be a CompatibilityReport or its to_dict() form. Returns a dict
    with allowed/block_level/overall/reason. A missing or malformed report is
    treated conservatively as not-allowed.
    """
    level = level or policy_from_settings()
    overall = _extract_overall(report)
    if overall is None:
        return {
            "allowed": False,
            "level": level.value,
            "overall": "unknown",
            "reason": "Uyumluluk raporu okunamadi (guvenli taraf: bloklu)",
        }
    block_at = _BLOCK_AT[level]
    blocked = _ORDER[overall] >= _ORDER[block_at]
    if blocked:
        reason = (f"{overall.value.upper()} seviyesinde uyumluluk bulgusu var;"
                  f" politika '{level.value}' bunu blokluyor")
    else:
        reason = f"Politika '{level.value}' izin verdi (esik: {block_at.value})"
    return {
        "allowed": not blocked,
        "level": level.value,
        "overall": overall.value,
        "reason": reason,
    }


def _extract_overall(report: Any) -> CheckSeverity | None:
    """Pull the overall severity from a report object or dict."""
    if report is None:
        return None
    # Object with an `overall` property (CompatibilityReport).
    overall = getattr(report, "overall", None)
    if isinstance(overall, CheckSeverity):
        return overall
    # Dict form (to_dict): derive from the checks' severities.
    if isinstance(report, dict):
        checks = report.get("checks", [])
        if not isinstance(checks, list):
            return None
        sev = CheckSeverity.PASS
        for c in checks:
            val = c.get("severity") if isinstance(c, dict) else None
            try:
                cs = CheckSeverity(val)
            except ValueError:
                continue
            if _ORDER[cs] > _ORDER[sev]:
                sev = cs
        return sev
    return None
