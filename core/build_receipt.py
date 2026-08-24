"""Faz 5 (F5.15) — build receipt: arac surumleri + debtap-db tarihi.

Donusum anindaki arac zincirini tanimlayan ve provenance/attest/SBOM'a
gomulen makbuz. Her proba best-effort'tur: bir arac yoksa ya da surumu
okunamazsa alan bos birakilir, asla raise etmez ve donusumu yavaslatmamak
icin kisa zaman asimi kullanir.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from config import ToolPaths, discover_tools

_VERSION_TIMEOUT_S = 3


def _first_line(cmd: list[str]) -> str:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=_VERSION_TIMEOUT_S, check=False)
        lines = (out.stdout or out.stderr).strip().splitlines()
        return lines[0].strip() if lines else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def debtap_db_date() -> str:
    """Return the mtime of the debtap database, or '' when not found."""
    candidates = [
        Path.home() / ".local" / "share" / "debtap" / "db",
        Path.home() / ".config" / "debtap" / "db",
        Path.home() / ".debtap" / "db",
        Path("/var/lib/debtap/db"),
    ]
    for cand in candidates:
        try:
            if cand.is_file():
                return time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(cand.stat().st_mtime))
        except OSError:
            continue
    return ""


def collect_build_receipt(tools: ToolPaths | None = None) -> dict[str, Any]:
    """Gather external tool versions + debtap-db date into a receipt dict."""
    tools = tools or discover_tools()
    probes = {
        "debtap": tools.debtap,
        "pacman": tools.pacman,
        "makepkg": tools.makepkg,
        "bsdtar": tools.bsdtar,
    }
    versions: dict[str, str] = {}
    for name, path in probes.items():
        if not path:
            continue
        line = _first_line([path, "--version"])
        if line:
            versions[name] = line
    return {
        "tool_versions": versions,
        "debtap_db_date": debtap_db_date(),
    }
