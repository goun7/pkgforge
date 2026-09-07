"""PkgForge — Safe package URL downloader.

Downloads .deb or .rpm packages directly from HTTP/HTTPS URLs into temporary storage.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from config import APP_VERSION, MAX_PACKAGE_SIZE_MB, create_temp_dir
from i18n import tr

log = logging.getLogger(__name__)


def _is_non_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for loopback/private/link-local/reserved/multicast — i.e. not Internet."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_public_host(hostname: str | None, *, allow_private_hosts: bool = False) -> None:
    """SSRF guard: refuse hosts that resolve to non-public addresses.

    A converter that installs packages as root must not fetch from
    attacker-influenced intranet addresses (169.254.169.254 cloud metadata,
    localhost admin panels, LAN routers). Literal IPs are checked directly;
    DNS names are resolved and every answer is checked (TOCTOU-noted:
    resolution happens per request, which also keeps balancer rotation working).

    Raises:
        ValueError: host is missing, unresolvable, or non-public (unless
            *allow_private_hosts* explicitly opts in for intranet use).
    """
    if not hostname:
        raise ValueError(tr("downloader.ssrf_bos_host"))
    if allow_private_hosts:
        return
    try:
        literal = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        literal = None
    candidates: list[str] = [str(literal)] if literal is not None else []
    if literal is None:
        try:
            infos = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC,
                                       type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError(
                tr("downloader.ssrf_cozulemedi", host=hostname)) from exc
        candidates = list({str(info[4][0]) for info in infos})
    for cand in candidates:
        try:
            ip = ipaddress.ip_address(cand.strip("[]"))
        except ValueError:
            continue
        if _is_non_public_ip(ip):
            raise ValueError(
                tr("downloader.ssrf_ozel_ag_reddedildi", host=hostname))
        return
    # Hicbir aday dogrulanamadi (örn. cozumleyici anlamsiz kayit dondu):
    # fail-closed — dogrulanamayan host'a inilmez.
    raise ValueError(tr("downloader.ssrf_cozulemedi", host=hostname))


class _SchemeGuardRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that re-validates the URL scheme on every hop.

    urllib follows 3xx redirects automatically; without this guard an
    ``https://`` download could be redirected to plain ``http://`` (or a
    non-HTTP scheme), bypassing the MITM protection applied to the
    user-supplied URL only.
    """

    def __init__(self, require_https: bool = True, allow_private_hosts: bool = False):
        super().__init__()
        self._require_https = require_https
        self._allow_private_hosts = allow_private_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                tr("downloader.yonlendirme_guvenli_olmayan_semaya", parsed_scheme=parsed.scheme)
            )
        if self._require_https and parsed.scheme != "https":
            raise ValueError(
                "Güvenlik: HTTPS indirme http:// adresine yönlendirilemez "
                "(MITM koruması). Yönlendirme reddedildi."
            )
        # F2.3: her atlamada SSRF kontrolu — ilk URL temiz olsa bile
        # yönlendirme intranet'e donebilir.
        assert_public_host(parsed.hostname,
                           allow_private_hosts=self._allow_private_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_url(
    req: urllib.request.Request,
    *,
    timeout: int = 30,
    require_https: bool = True,
    allow_private_hosts: bool = False,
):
    """Open *req* through an opener that guards redirects.

    The redirect guard re-validates the URL scheme on every 3xx hop so an
    ``https://`` download cannot be downgraded to ``http://`` (MITM) or
    escape to a non-HTTP scheme. Kept as a separate function so tests can
    patch it without touching global urllib state.
    """
    opener = urllib.request.build_opener(
        _SchemeGuardRedirectHandler(require_https=require_https,
                                    allow_private_hosts=allow_private_hosts)
    )
    return opener.open(req, timeout=timeout)  # nosec B310


def _validate_download_url(url: str, require_https: bool,
                           allow_private_hosts: bool = False) -> urllib.parse.ParseResult:
    """URL semasini dogrular; HTTPS zorunluysa plain http reddedilir.

    Guvenlik: paketler kok olarak kurulacagi icin MITM degisimi engellenmeli;
    gelismis kullanicilar allow_insecure_http ayariyla devre disi birakabilir.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(tr("downloader.gecersiz_url_semasi_parsed", parsed_scheme=parsed.scheme))
    if require_https and parsed.scheme != "https":
        raise ValueError(
            "Güvenlik: yalnızca HTTPS bağlantıları kabul edilir. "
            "http'yi etkinleştirmek için ayarlardan 'allow_insecure_http' seçeneğini açın."
        )
    assert_public_host(parsed.hostname, allow_private_hosts=allow_private_hosts)
    return parsed


def _download_filename(url: str, parsed: urllib.parse.ParseResult) -> str:
    """URL yolundan taban-ad cikarir (traversal imkansiz; varsayilani guvenli)."""
    filename = Path(parsed.path).name
    if not filename or "." not in filename:
        filename = "downloaded_package.deb" if "deb" in url.lower() else "downloaded_package.rpm"
    return filename


def _verify_download_sha256(dest_file: Path, expected_sha256: str) -> None:
    """Bilinen SHA-256 ile indirmeyi teyit eder; uyusmazlikta dosyayi siler.

    Karsilastirma buyuk/kucuk harf duyarsizdir (F5.9).
    """
    from core.security import sha256_hash
    actual = sha256_hash(dest_file)
    if actual.lower() != expected_sha256.strip().lower():
        dest_file.unlink(missing_ok=True)
        raise ValueError(
            tr("downloader.sha_256_dogrulamasi_basarisiz", var0=expected_sha256.strip()[:16], actual=actual[:16])
        )
    log.info(tr("downloader.sha_256_dogrulandi_s"), actual[:16])


def download_package(
    url: str,
    dest_dir: Path | None = None,
    *,
    require_https: bool = True,
    expected_sha256: str | None = None,
    response_info: dict[str, str] | None = None,
    allow_private_hosts: bool = False,
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
        response_info: Optional dict to receive HTTP response metadata
            (``etag``, ``last_modified``, ``content_length``). Used by
            the upstream tracker to detect future updates.
        allow_private_hosts: When True, permit downloads from loopback,
            LAN and other non-public addresses (intranet mirrors). Default
            False — SSRF protection for a tool that installs as root.

    Returns:
        Path to the downloaded file.
    """
    parsed = _validate_download_url(url, require_https, allow_private_hosts)
    filename = _download_filename(url, parsed)

    if dest_dir is None:
        dest_dir = create_temp_dir()

    dest_file = dest_dir / filename
    log.info("Paket indiriliyor: %s → %s", url, dest_file)

    req = urllib.request.Request(url, headers={"User-Agent": f"PkgForge/{APP_VERSION}"})
    max_bytes = MAX_PACKAGE_SIZE_MB * 1024 * 1024
    downloaded_bytes = 0

    # Retry with exponential backoff for network errors
    from core.retry import RetryConfig, retry_with_backoff

    def _do_download():
        nonlocal downloaded_bytes
        downloaded_bytes = 0
        with _open_url(req, timeout=30, require_https=require_https,
                      allow_private_hosts=allow_private_hosts) as resp:
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise ValueError(tr("downloader.dosya_boyutu_cok_buyuk", var0=int(content_length) / (1024*1024)))

            # Capture HTTP caching headers for upstream update tracking
            if response_info is not None:
                response_info["etag"] = resp.headers.get("ETag", "").strip('"')
                response_info["last_modified"] = resp.headers.get("Last-Modified", "")
                response_info["content_length"] = content_length or ""

            with open(dest_file, "wb") as out_f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > max_bytes:
                        raise ValueError("İndirme boyutu maksimum limiti aştı")
                    out_f.write(chunk)

    retry_config = RetryConfig(
        max_retries=3,
        base_delay=2.0,
        retryable_exceptions=(urllib.error.URLError, ConnectionError, TimeoutError, OSError),
    )
    try:
        retry_with_backoff(_do_download, config=retry_config, operation_name=f"download({filename})")
    except Exception as exc:  # noqa: BLE001
        log.error(tr("downloader.i_ndirme_basarisiz_3_deneme"), exc)
        raise RuntimeError(tr("downloader.ndirme_basarisiz_exc", exc=exc))

    # Optional integrity verification against a known SHA-256
    if expected_sha256:
        _verify_download_sha256(dest_file, expected_sha256)

    log.info(tr("downloader.i_ndirme_tamamlandi_s_d"), dest_file.name, downloaded_bytes)
    return dest_file
