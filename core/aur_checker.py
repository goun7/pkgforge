"""PkgForge — AUR version checker.

Queries the AUR RPC API to check if a package exists and compare
versions, helping users decide if conversion is necessary.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Literal

from config import AUR_RPC_URL, APP_VERSION

log = logging.getLogger(__name__)


@dataclass
class AurResult:
    """Result of an AUR version check."""
    status: Literal["found_newer", "found_older", "out_of_date", "not_found", "error"]
    aur_version: str = ""
    out_of_date: bool = False
    last_modified: str = ""
    detail: str = ""


def check_aur(package_name: str, local_version: str = "") -> AurResult:
    """Check AUR for a package and compare versions.

    Args:
        package_name: The package name to search for.
        local_version: The version from the .deb/.rpm being converted.

    Returns:
        AurResult with status and version info.
    """
    if not package_name:
        return AurResult(status="error", detail="Boş paket adı")

    try:
        url = f"{AUR_RPC_URL}?arg[]={urllib.request.quote(package_name)}"
        req = urllib.request.Request(url, headers={"User-Agent": f"PkgForge/{APP_VERSION}"})

        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("resultcount", 0) == 0:
            return AurResult(status="not_found")

        pkg_info = data["results"][0]
        aur_ver = pkg_info.get("Version", "")
        ood = pkg_info.get("OutOfDate") is not None
        last_mod = pkg_info.get("LastModified", "")

        result = AurResult(
            aur_version=aur_ver,
            out_of_date=ood,
            last_modified=str(last_mod),
        )

        if ood:
            result.status = "out_of_date"
        elif local_version and _version_compare(aur_ver, local_version) >= 0:
            result.status = "found_newer"
        else:
            result.status = "found_older"

        log.info("AUR check: %s → %s (aur: %s, local: %s)",
                 package_name, result.status, aur_ver, local_version)
        return result

    except urllib.error.URLError as exc:
        log.warning("AUR sorgusu başarısız: %s", exc)
        return AurResult(status="error", detail=str(exc))
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        log.warning("AUR yanıtı ayrıştırılamadı: %s", exc)
        return AurResult(status="error", detail=str(exc))


def _version_compare(ver_a: str, ver_b: str) -> int:
    """Compare Arch version strings. Returns >0 if ver_a > ver_b, <0 if ver_a < ver_b, 0 if equal.

    Uses pacman's `vercmp` binary if available, falling back to a structured comparison.
    """
    import shutil
    from core.security import safe_run

    vercmp_bin = shutil.which("vercmp")
    if vercmp_bin:
        try:
            res = safe_run([vercmp_bin, ver_a, ver_b], timeout=5)
            if res.returncode == 0:
                out = res.stdout.strip()
                if out:
                    return int(out)
        except (ValueError, Exception) as exc:
            log.warning("vercmp çalıştırma hatası: %s", exc)

    # Fallback Python version comparison
    import re

    def _normalize(v: str) -> list[int]:
        v = re.sub(r"^\d+:", "", v)
        if "-" in v:
            v = v.rsplit("-", 1)[0]
        parts = re.findall(r"\d+", v)
        return [int(p) for p in parts]

    a_parts = _normalize(ver_a)
    b_parts = _normalize(ver_b)

    for a, b in zip(a_parts, b_parts):
        if a != b:
            return a - b

    return len(a_parts) - len(b_parts)

