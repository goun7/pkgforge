"""PkgForge — Cross-Check Engine.

Compares package versions across Local file/installation, AUR, and Flatpak using vercmp
to recommend the overall newest available version regardless of distribution channel.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass

from core.aur_checker import _version_compare, check_aur
from core.security import safe_run
from i18n import tr

log = logging.getLogger(__name__)


@dataclass
class SourceInfo:
    channel: str  # "local", "aur", "flatpak"
    version: str
    available: bool = False
    details: str = ""


@dataclass
class CrossCheckReport:
    package_name: str
    local_version: str
    aur_version: str
    flatpak_version: str
    recommended_source: str  # "local", "aur", "flatpak"
    recommendation_reason: str


def cross_check_package(package_name: str, local_version: str = "") -> CrossCheckReport:
    """Compare local package version against AUR and Flatpak versions.

    Args:
        package_name: Name of the package.
        local_version: Local package or file version.

    Returns:
        CrossCheckReport with version comparison and recommendation.
    """
    # 1. AUR check
    aur_res = check_aur(package_name, local_version)
    aur_ver = aur_res.aur_version if aur_res.status != "not_found" and aur_res.status != "error" else ""

    # 2. Flatpak check
    flatpak_ver = _query_flatpak_version(package_name)

    # 3. Determine best source using _version_compare (vercmp)
    best_source = "local"
    best_ver = local_version or "0.0.0"
    reason = "Yerel paket güncel veya tek kaynak."

    if aur_ver and _version_compare(aur_ver, best_ver) > 0:
        best_source = "aur"
        best_ver = aur_ver
        reason = tr("cross.aur_da_daha_yeni", aur_ver=aur_ver, local_version=local_version)

    if flatpak_ver and _version_compare(flatpak_ver, best_ver) > 0:
        best_source = "flatpak"
        best_ver = flatpak_ver
        reason = tr("cross.flatpak_deposunda_daha_yeni", flatpak_ver=flatpak_ver)

    log.info(
        "Cross-check for %s: local=%s, aur=%s, flatpak=%s → recommendation: %s",
        package_name, local_version, aur_ver, flatpak_ver, best_source
    )

    return CrossCheckReport(
        package_name=package_name,
        local_version=local_version,
        aur_version=aur_ver,
        flatpak_version=flatpak_ver,
        recommended_source=best_source,
        recommendation_reason=reason,
    )


def _query_flatpak_version(package_name: str) -> str:
    """Query flatpak CLI for package version if flatpak is installed."""
    flatpak_bin = shutil.which("flatpak")
    if not flatpak_bin or not package_name:
        return ""

    try:
        # '--' keeps a crafted package name from being parsed as a flag
        res = safe_run([flatpak_bin, "search", "--", package_name], timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.splitlines()[1:]:  # skip header
                parts = line.split("\t")
                if len(parts) >= 4:
                    name_id = parts[0].strip().lower()
                    version = parts[3].strip() if len(parts) > 3 else ""
                    if package_name.lower() in name_id and version:
                        return version
    except Exception as exc:  # noqa: BLE001
        log.warning(tr("cross.flatpak_sorgusu_basarisiz_s"), exc)

    return ""
