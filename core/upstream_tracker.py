"""PkgForge — Upstream Auto-Tracker.

Performs lightweight HTTP HEAD requests to check ETag/Last-Modified headers of saved
package download URLs without downloading full packages.
"""

from __future__ import annotations

import logging
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any

from core.history_db import HistoryDB, HistoryRecord
from config import APP_VERSION

log = logging.getLogger(__name__)


@dataclass
class UpdateCheckResult:
    """Result of checking an upstream URL for package updates."""
    package_name: str
    source_url: str
    has_update: bool
    status: str
    etag: str = ""
    last_modified: str = ""
    content_length: str = ""
    detail: str = ""


def check_upstream_update(record: HistoryRecord) -> UpdateCheckResult:
    """Check a single package's download URL for updates via HTTP HEAD request."""
    if not record.source_url or not record.source_url.startswith(("http://", "https://")):
        return UpdateCheckResult(
            package_name=record.package_name,
            source_url=record.source_url,
            has_update=False,
            status="no_url",
            detail="Geçerli indirme URL'si yok (http/https gerekli)",
        )

    try:
        req = urllib.request.Request(
            record.source_url,
            method="HEAD",
            headers={"User-Agent": f"PkgForge/{APP_VERSION}"},
        )

        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            headers = resp.headers
            etag = headers.get("ETag", "").strip('"')
            last_mod = headers.get("Last-Modified", "")
            content_len = headers.get("Content-Length", "")

            # If Last-Modified is present, log it
            log.info(
                "Upstream HEAD check for %s: ETag=%s, Last-Modified=%s",
                record.package_name,
                etag,
                last_mod,
            )

            # Determine update status based on ETag or Last-Modified if recorded
            has_update = bool(etag or last_mod)
            return UpdateCheckResult(
                package_name=record.package_name,
                source_url=record.source_url,
                has_update=has_update,
                status="checked",
                etag=etag,
                last_modified=last_mod,
                content_length=content_len,
                detail=f"Last-Modified: {last_mod}" if last_mod else "Upstream erişilebilir",
            )

    except urllib.error.URLError as exc:
        log.warning("Upstream sorgusu başarısız (%s): %s", record.package_name, exc)
        return UpdateCheckResult(
            package_name=record.package_name,
            source_url=record.source_url,
            has_update=False,
            status="error",
            detail=str(exc),
        )


def check_all_installed_updates() -> list[UpdateCheckResult]:
    """Check all packages in HistoryDB with registered source URLs for updates."""
    db = HistoryDB()
    records = db.get_history(limit=100)
    results: list[UpdateCheckResult] = []

    seen_pkgs = set()
    for rec in records:
        if rec.package_name not in seen_pkgs and rec.source_url:
            seen_pkgs.add(rec.package_name)
            res = check_upstream_update(rec)
            results.append(res)

    return results
