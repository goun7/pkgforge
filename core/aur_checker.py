"""PkgForge — AUR version checker.

Queries the AUR RPC API to check if a package exists and compare
versions, helping users decide if conversion is necessary.
"""

from __future__ import annotations

import json
import logging
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Literal

from config import APP_VERSION, AUR_RPC_URL, AUR_SEARCH_URL
from i18n import tr

log = logging.getLogger(__name__)


@dataclass
class AurResult:
    """Result of an AUR version check."""
    status: Literal["found_newer", "found_older", "out_of_date", "not_found", "error"]
    aur_version: str = ""
    out_of_date: bool = False
    last_modified: str = ""
    detail: str = ""


def check_aur(package_name: str, local_version: str = "", offline: bool = False) -> AurResult:
    """Check AUR for a package and compare versions.

    Args:
        package_name: The package name to search for.
        local_version: The version from the .deb/.rpm being converted.
        offline: If True, skip network request and return cached/error result.

    Returns:
        AurResult with status and version info.
    """
    if not package_name:
        return AurResult(status="error", detail="Boş paket adı")

    if offline:
        log.info(tr("aur_check.cevrimdisi_mod_aur_kontrolu_atlandi"), package_name)
        return AurResult(status="error", detail="Çevrimdışı mod — ağ erişimi yok")

    try:
        url = f"{AUR_RPC_URL}?arg[]={urllib.parse.quote(package_name)}"
        req = urllib.request.Request(url, headers={"User-Agent": f"PkgForge/{APP_VERSION}"})

        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("resultcount", 0) == 0:
            return AurResult(status="not_found")

        pkg_info = data["results"][0]
        aur_ver = pkg_info.get("Version", "")
        ood = pkg_info.get("OutOfDate") is not None
        last_mod = pkg_info.get("LastModified", "")

        status: Literal["found_newer", "found_older", "out_of_date", "not_found", "error"] = "error"
        if ood:
            status = "out_of_date"
        elif local_version and _version_compare(aur_ver, local_version) >= 0:
            status = "found_newer"
        else:
            status = "found_older"

        result = AurResult(
            status=status,
            aur_version=aur_ver,
            out_of_date=ood,
            last_modified=str(last_mod),
        )

        log.info("AUR check: %s → %s (aur: %s, local: %s)",
                 package_name, result.status, aur_ver, local_version)
        return result

    except urllib.error.URLError as exc:
        log.warning(tr("aur_check.aur_sorgusu_basarisiz_s"), exc)
        return AurResult(status="error", detail=str(exc))
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        log.warning(tr("aur_check.aur_yaniti_ayristirilamadi_s"), exc)
        return AurResult(status="error", detail=str(exc))


def search_aur(query: str, limit: int = 25, offline: bool = False) -> list[dict]:
    """Search the AUR RPC API for packages matching a query.

    Args:
        query: Search term (matched against name/description by AUR).
        limit: Maximum number of results to return.
        offline: If True, skip network request and return an empty list.

    Returns:
        List of dicts: name, version, description, num_votes, out_of_date, url_path.
    """
    if not query or not query.strip():
        return []
    if offline:
        log.info(tr("aur_check.cevrimdisi_mod_aur_aramasi_atlandi"), query)
        return []

    try:
        url = f"{AUR_SEARCH_URL}?arg={urllib.parse.quote(query.strip())}"
        req = urllib.request.Request(url, headers={"User-Agent": f"PkgForge/{APP_VERSION}"})

        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8"))

        results: list[dict] = []
        for pkg in data.get("results", [])[: max(1, limit)]:
            results.append({
                "name": pkg.get("Name", ""),
                "version": pkg.get("Version", ""),
                "description": pkg.get("Description", "") or "",
                "num_votes": int(pkg.get("NumVotes", 0)),
                "out_of_date": pkg.get("OutOfDate") is not None,
                "url_path": pkg.get("URLPath", ""),
            })
        # Most-voted first for relevance.
        results.sort(key=lambda r: r["num_votes"], reverse=True)
        log.info(tr("aur_check.aur_arama_r_d_sonuc"), query, len(results))
        return results

    except urllib.error.URLError as exc:
        log.warning(tr("aur_check.aur_aramasi_basarisiz_s"), exc)
        return []
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        log.warning(tr("aur_check.aur_arama_yaniti_ayristirilamadi_s"), exc)
        return []


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
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            log.warning(tr("aur_check.vercmp_calistirma_hatasi_s"), exc)

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

