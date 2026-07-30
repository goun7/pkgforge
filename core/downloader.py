"""PkgForge — Safe package URL downloader.

Downloads .deb or .rpm packages directly from HTTP/HTTPS URLs into temporary storage.
"""

from __future__ import annotations

import logging
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

from config import MAX_PACKAGE_SIZE_MB, create_temp_dir

log = logging.getLogger(__name__)


def download_package(
    url: str,
    dest_dir: Path | None = None,
    *,
    require_https: bool = True,
    expected_sha256: str | None = None,
) -> Path:
    """Download a package file from a URL.

    Args:
        url: Direct HTTP/HTTPS download link.
        dest_dir: Target directory. If None, a temporary directory is created.
        require_https: When True (default) plain ``http://`` is rejected so a
            man-in-the-middle cannot swap the package that will be installed
            as root. Advanced users may opt out via the ``allow_insecure_http``
            setting.
        expected_sha256: If provided, the downloaded file's SHA-256 must match
            (case-insensitive) or the file is deleted and an error is raised.

    Returns:
        Path to the downloaded file.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Geçersiz URL şeması: {parsed.scheme}. Yalnızca http ve https desteklenir.")
    if require_https and parsed.scheme != "https":
        raise ValueError(
            "Güvenlik: yalnızca HTTPS bağlantıları kabul edilir. "
            "http'yi etkinleştirmek için ayarlardan 'allow_insecure_http' seçeneğini açın."
        )

    # Extract filename from path (basename only — never a traversal path)
    filename = Path(parsed.path).name
    if not filename or "." not in filename:
        filename = "downloaded_package.deb" if "deb" in url.lower() else "downloaded_package.rpm"

    if dest_dir is None:
        dest_dir = create_temp_dir()

    dest_file = dest_dir / filename
    log.info("Paket indiriliyor: %s → %s", url, dest_file)

    req = urllib.request.Request(url, headers={"User-Agent": "PkgForge/2.0"})
    max_bytes = MAX_PACKAGE_SIZE_MB * 1024 * 1024
    downloaded_bytes = 0

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise ValueError(f"Dosya boyutu çok büyük: {int(content_length) / (1024*1024):.1f} MB")

            with open(dest_file, "wb") as out_f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > max_bytes:
                        raise ValueError("İndirme boyutu maksimum limiti aştı")
                    out_f.write(chunk)

    except urllib.error.URLError as exc:
        log.error("İndirme başarısız: %s", exc)
        raise RuntimeError(f"İndirme başarısız: {exc}")

    # Optional integrity verification against a known SHA-256
    if expected_sha256:
        from core.security import sha256_hash
        actual = sha256_hash(dest_file)
        if actual.lower() != expected_sha256.strip().lower():
            dest_file.unlink(missing_ok=True)
            raise ValueError(
                f"SHA-256 doğrulaması başarısız: beklenen {expected_sha256.strip()[:16]}…, "
                f"gerçek {actual[:16]}…"
            )
        log.info("SHA-256 doğrulandı: %s", actual[:16])

    log.info("İndirme tamamlandı: %s (%d bayt)", dest_file.name, downloaded_bytes)
    return dest_file
