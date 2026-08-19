"""PkgForge — Binary Differential Updates.

When downloading a new version of a package that we already have locally,
compute a binary delta (xdelta3) so only the diff needs to be downloaded.
This can reduce bandwidth by 80-95% for point releases.

Requires ``xdelta3`` to be installed (pacman -S xdelta3).
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from core.security import safe_run

log = logging.getLogger(__name__)


def is_xdelta3_available() -> bool:
    """Return True if xdelta3 is installed."""
    return shutil.which("xdelta3") is not None


def create_delta(old_file: Path, new_file: Path, delta_file: Path) -> bool:
    """Create a binary delta from old_file to new_file.

    Args:
        old_file: The current/old version of the file.
        new_file: The new version of the file.
        delta_file: Output path for the delta.

    Returns:
        True if delta was created successfully.
    """
    if not is_xdelta3_available():
        log.warning("xdelta3 bulunamadı — delta oluşturulamıyor")
        return False

    if not old_file.is_file() or not new_file.is_file():
        return False

    res = safe_run(
        ["xdelta3", "-e", "-f", "-s", str(old_file), str(new_file), str(delta_file)],
        timeout=300,
    )

    if res.returncode != 0:
        log.warning("xdelta3 delta oluşturma başarısız (kod %d): %s",
                    res.returncode, res.stderr[:200])
        return False

    old_size = old_file.stat().st_size
    new_size = new_file.stat().st_size
    delta_size = delta_file.stat().st_size
    ratio = (1 - delta_size / new_size) * 100 if new_size > 0 else 0

    log.info("Delta oluşturuldu: %s → %s (%d bayt, %.0f%% tasarruf)",
             old_file.name, delta_file.name, delta_size, ratio)
    return True


def apply_delta(old_file: Path, delta_file: Path, output_file: Path) -> bool:
    """Apply a binary delta to reconstruct the new file.

    Args:
        old_file: The current/old version of the file.
        delta_file: The delta file to apply.
        output_file: Output path for the reconstructed file.

    Returns:
        True if delta was applied successfully.
    """
    if not is_xdelta3_available():
        return False

    if not old_file.is_file() or not delta_file.is_file():
        return False

    res = safe_run(
        ["xdelta3", "-d", "-f", "-s", str(old_file), str(delta_file), str(output_file)],
        timeout=300,
    )

    if res.returncode != 0:
        log.warning("xdelta3 delta uygulama başarısız (kod %d): %s",
                    res.returncode, res.stderr[:200])
        return False

    log.info("Delta uygulandı: %s + %s → %s",
             old_file.name, delta_file.name, output_file.name)
    return True


def find_local_previous(package_name: str, pkg_dir: Path | None = None) -> Path | None:
    """Search for a previously downloaded version of the same package.

    Looks in the conversion history backups and the specified directory.
    """
    if pkg_dir is None:
        from config import CONFIG_DIR
        pkg_dir = CONFIG_DIR / "backups"

    if not pkg_dir.is_dir():
        return None

    # Search for matching package files (same base name, different version)
    candidates: list[Path] = []
    for f in pkg_dir.iterdir():
        if not f.is_file():
            continue
        if ".pkg.tar" in f.name:
            # Match by base package name (strip version)
            base = f.name.split("-")[0] if "-" in f.name else f.stem
            if base and base.lower() in package_name.lower():
                candidates.append(f)

    # Return the most recent one (by modification time)
    if candidates:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]

    return None


def download_with_delta(
    url: str,
    dest_file: Path,
    old_file: Path | None = None,
    *,
    require_https: bool = True,
) -> tuple[Path, bool]:
    """Download a file using delta if a local previous version exists.

    Args:
        url: Direct download URL.
        dest_file: Where to save the final file.
        old_file: Previous version (if available locally).
        require_https: Require HTTPS.

    Returns:
        (final_path, used_delta)
    """
    from core.downloader import download_package

    if old_file is None or not old_file.is_file() or not is_xdelta3_available():
        # No delta possible — full download
        result = download_package(url, dest_file.parent, require_https=require_https)
        return result, False

    # Try to download delta first (URL pattern: same URL + .xdelta suffix)
    delta_url = url + ".xdelta"
    with tempfile.TemporaryDirectory(prefix="pkgforge_delta_") as tmpdir:
        delta_file = Path(tmpdir) / "delta.xdelta"

        try:
            download_package(delta_url, Path(tmpdir),
                           require_https=require_https)
            # If we got here, delta was downloaded
            if apply_delta(old_file, delta_file, dest_file):
                log.info("Delta indirme başarılı: %s", dest_file.name)
                return dest_file, True
        except Exception:
            log.info("Delta indirilemedi, tam dosya indiriliyor: %s", url)

    # Fallback to full download
    result = download_package(url, dest_file.parent, require_https=require_https)
    return result, False
