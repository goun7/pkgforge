"""PkgForge — Upstream Auto-Tracker.

Performs lightweight HTTP HEAD requests to check ETag/Last-Modified headers of saved
package download URLs without downloading full packages.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from config import APP_VERSION
from core.history_db import HistoryDB, HistoryRecord
from i18n import tr

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
    record_id: int = 0


def check_upstream_update(record: HistoryRecord, offline: bool = False) -> UpdateCheckResult:
    """Check a single package's download URL for updates via HTTP HEAD request.

    Compares the current ETag/Last-Modified against stored values to detect
    actual content changes on the upstream server.

    Args:
        record: History record with source URL and ETag info.
        offline: If True, skip network request and return cached result.
    """
    if offline:
        return UpdateCheckResult(
            package_name=record.package_name,
            source_url=record.source_url,
            has_update=False,
            status="offline",
            detail="Çevrimdışı mod — güncelleme kontrolü atlandı",
        )

    if not record.source_url or not record.source_url.startswith(("http://", "https://")):
        return UpdateCheckResult(
            package_name=record.package_name,
            source_url=record.source_url,
            has_update=False,
            status="no_url",
            detail="Geçerli indirme URL'si yok (http/https gerekli)",
        )

    try:
        from core.downloader import _open_url, assert_public_host
        from core.retry import RetryConfig, retry_with_backoff

        parsed = urllib.parse.urlparse(record.source_url)
        # F2.3: HEAD kontrolu de SSRF yuzeyi — intranet URL'ler reddedilir.
        # Kayitli URL kullanicinin kendi gecmisinden gelse bile, zararli bir
        # .deb'in icine gomulu intranet URL sonradan sorgulanabilirdi.
        assert_public_host(parsed.hostname)

        def _do_head() -> Any:
            req = urllib.request.Request(
                record.source_url,
                method="HEAD",
                headers={"User-Agent": f"PkgForge/{APP_VERSION}"},
            )
            return _open_url(req, timeout=10)

        retry_config = RetryConfig(
            max_retries=2,
            base_delay=1.0,
            retryable_exceptions=(urllib.error.URLError, ConnectionError, TimeoutError, OSError),
        )
        resp = retry_with_backoff(_do_head, config=retry_config, operation_name="upstream-HEAD")

        with resp:
            headers = resp.headers
            etag = headers.get("ETag", "").strip('"')
            last_mod = headers.get("Last-Modified", "")
            content_len = headers.get("Content-Length", "")

            log.info(
                "Upstream HEAD check for %s: ETag=%s, Last-Modified=%s",
                record.package_name,
                etag,
                last_mod,
            )

            # Compare against stored values to detect actual changes
            prev_etag = record.http_etag
            prev_last_mod = record.http_last_modified

            has_update = False
            detail = ""

            if prev_etag and etag and prev_etag != etag:
                has_update = True
                detail = tr("upstream.etag_degisti_prev_etag", prev_etag=prev_etag[:20], etag=etag[:20])
            elif prev_last_mod and last_mod and prev_last_mod != last_mod:
                has_update = True
                detail = tr("upstream.last_modified_degisti_prev", prev_last_mod=prev_last_mod, last_mod=last_mod)
            elif not prev_etag and not prev_last_mod:
                # İlk kayıt — sakla ama güncelleme olarak işaretleme
                detail = "İlk kontrol — upstream erişilebilir"
            else:
                detail = "Değişiklik tespit edilmedi"

            return UpdateCheckResult(
                package_name=record.package_name,
                source_url=record.source_url,
                has_update=has_update,
                status="checked",
                etag=etag,
                last_modified=last_mod,
                content_length=content_len,
                detail=detail,
                record_id=record.id,
            )

    except urllib.error.URLError as exc:
        log.warning(tr("upstream.upstream_sorgusu_basarisiz_s_s"), record.package_name, exc)
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
            # Saklanan değerleri güncelle (sonraki kontrol için)
            if res.record_id and res.status == "checked":
                db.update_http_headers(res.record_id, res.etag, res.last_modified)

    return results
