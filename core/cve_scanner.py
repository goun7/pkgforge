"""PkgForge — CVE / vulnerability scanner (Faz 2 / B4).

Compares a package's dependency list against known vulnerabilities using
the free, keyless OSV.dev API. Degrades gracefully when offline.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from config import APP_VERSION
from i18n import tr

log = logging.getLogger(__name__)

OSV_QUERY_URL = "https://api.osv.dev/v1/query"


def _query_osv(dep_name: str, timeout: int = 10) -> list[dict]:
    """Query OSV.dev for vulnerabilities affecting a single dependency.

    Returns a list of raw vuln dicts (empty on any failure).
    """
    body = json.dumps({"package": {"name": dep_name}}).encode("utf-8")
    req = urllib.request.Request(
        OSV_QUERY_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"PkgForge/{APP_VERSION}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("vulns", [])
    except urllib.error.URLError as exc:
        log.warning(tr("cve.osv_sorgusu_basarisiz_s_s"), dep_name, exc)
        raise
    except (json.JSONDecodeError, KeyError) as exc:
        log.warning(tr("cve.osv_yaniti_ayristirilamadi_s_s"), dep_name, exc)
        return []


def scan_dependencies(deps: list[str], offline: bool = False) -> dict:
    """Scan a list of dependency names for known vulnerabilities.

    Args:
        deps: Dependency names (e.g. from package_analyzer.depends).
        offline: If True, skip network and report offline.

    Returns:
        Dict: package, deps_scanned, vulns[{id, summary, severity, affected_dep}],
        count, offline.
    """
    result: dict = {
        "package": "",
        "deps_scanned": 0,
        "vulns": [],
        "count": 0,
        "offline": False,
    }

    clean = [d for d in deps if d and d.strip()]
    result["deps_scanned"] = len(clean)
    if not clean:
        return result

    if offline:
        log.info(tr("cve.cevrimdisi_mod_cve_taramasi_atlandi"))
        result["offline"] = True
        return result

    seen_ids: set[str] = set()
    vulns: list[dict] = []
    hit_network_error = False

    for dep in clean:
        try:
            raw = _query_osv(dep)
        except urllib.error.URLError:
            hit_network_error = True
            continue

        for v in raw:
            vid = v.get("id", "")
            if not vid or vid in seen_ids:
                continue
            seen_ids.add(vid)
            severity = (
                v.get("database_specific", {}).get("severity")
                or v.get("severity", [{}])[0].get("type", "")
                or "UNKNOWN"
            )
            vulns.append({
                "id": vid,
                "summary": v.get("summary", "") or "",
                "severity": str(severity),
                "affected_dep": dep,
            })

    if hit_network_error and not vulns:
        # SEC: ag hatasinda "temiz" varsayma — cagiran bunu offline/guvenilmez
        # sayar (fail-open yok).
        result["offline"] = True
        result["network_error"] = True

    result["vulns"] = vulns
    result["count"] = len(vulns)
    log.info(tr("cve.cve_taramasi_d_bagimlilik_d"), len(clean), len(vulns))
    return result


def scan_package(pkg_path, tools) -> dict:
    """Extract dependencies from a package and scan them for CVEs.

    Args:
        pkg_path: Path to a .deb/.rpm/.pkg.tar.zst file.
        tools: ToolPaths from discover_tools().

    Returns:
        scan_dependencies() result with 'package' set to the file name.
    """
    from pathlib import Path

    from core.package_analyzer import analyze_package

    path = Path(pkg_path)
    try:
        meta = analyze_package(path, tools)
        deps = list(meta.depends)
    except Exception as exc:  # noqa: BLE001 — analyzer may raise many types
        log.warning("Paket analiz edilemedi (%s): %s", path, exc)
        deps = []

    result = scan_dependencies(deps)
    result["package"] = path.name
    return result
