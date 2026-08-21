"""PkgForge — Plugin Marketplace.

Download and install community converter plugins from GitHub releases.

Usage:
    from core.plugins.marketplace import install_plugin, list_installed_plugins
    path = install_plugin("flatpak-converter")
    plugins = list_installed_plugins()
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

# GitHub org and repo for community plugins
PLUGIN_ORG = "pkgforge"
PLUGIN_REPO = "pkgforge-plugins"
PLUGIN_RELEASE_URL = f"https://github.com/{PLUGIN_ORG}/{PLUGIN_REPO}/releases/download"
PLUGIN_INDEX_URL = f"https://api.github.com/repos/{PLUGIN_ORG}/{PLUGIN_REPO}/releases/latest"

# Local plugin install directory
PLUGIN_DIR = Path.home() / ".config" / "pkgforge" / "plugins"

# Strict plugin name: lowercase alphanumerics, '-' and '_' only, 1-64 chars.
# Prevents path traversal (e.g. "../../evil") when building PLUGIN_DIR paths.
_PLUGIN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def is_valid_plugin_name(name: str) -> bool:
    """Return True if *name* is a safe plugin identifier."""
    return bool(name) and _PLUGIN_NAME_RE.match(name) is not None


def _validate_plugin_name(name: str) -> None:
    """Raise ValueError if *name* is not a safe plugin identifier."""
    if not is_valid_plugin_name(name):
        raise ValueError(
            f"Geçersiz plugin adı: {name!r}. "
            f"Yalnızca küçük harf, rakam, '-' ve '_' içeren 1-64 karakterlik adlar kabul edilir."
        )


def _require_https(url: str) -> None:
    """Raise ValueError unless *url* uses the https scheme."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Güvenlik: plugin indirme yalnızca HTTPS üzerinden yapılır: {url}")


def _get_user_agent() -> str:
    """Build user-agent string."""
    from config import APP_NAME, APP_VERSION
    return f"{APP_NAME}/{APP_VERSION} (plugin-marketplace)"


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_file(url: str, dest: Path, timeout: int = 30) -> None:
    """Download a URL to a local path (HTTPS only)."""
    _require_https(url)
    req = urllib.request.Request(url, headers={"User-Agent": _get_user_agent()})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        with open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)


def _fetch_json(url: str, timeout: int = 10) -> dict:
    """Fetch JSON from a URL (HTTPS only)."""
    _require_https(url)
    req = urllib.request.Request(url, headers={"User-Agent": _get_user_agent()})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return json.loads(resp.read().decode("utf-8"))


def fetch_available_plugins(offline: bool = False) -> list[dict[str, str]]:
    """Fetch list of available plugins from GitHub releases.

    Args:
        offline: If True, return empty list without network request.

    Returns:
        List of dicts with 'name', 'version', 'description', 'download_url', 'sha256_url'.
    """
    if offline:
        log.info("Çevrimdışı mod — plugin listesi atlandı")
        return []
    try:
        data = _fetch_json(PLUGIN_INDEX_URL)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        log.warning("Plugin index fetch failed: %s", exc)
        return []

    plugins: list[dict[str, str]] = []
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if not name.endswith(".py"):
            continue
        # Plugin name is the asset filename without .py
        plugin_name = name.rsplit(".", 1)[0]
        download_url = asset.get("browser_download_url", "")
        plugins.append({
            "name": plugin_name,
            "version": data.get("tag_name", "unknown"),
            "description": f"Community plugin: {plugin_name}",
            "download_url": download_url,
            "sha256_url": f"{download_url}.sha256",
        })

    return plugins


def install_plugin(
    name: str,
    *,
    version: str = "latest",
    verify_checksum: bool = True,
    force: bool = False,
) -> Path:
    """Install a plugin from the marketplace.

    Args:
        name: Plugin name (e.g., "flatpak-converter").
        version: Version to install (default: "latest").
        verify_checksum: Whether to verify SHA-256 checksum.
        force: Overwrite existing plugin.

    Returns:
        Path to the installed plugin file.

    Raises:
        ValueError: Plugin name is not a safe identifier.
        FileNotFoundError: Plugin not found in marketplace.
        RuntimeError: Download or verification failed.
    """
    _validate_plugin_name(name)
    PLUGIN_DIR.mkdir(parents=True, exist_ok=True)

    dest = PLUGIN_DIR / f"{name}.py"

    # Check if already installed
    if dest.exists() and not force:
        log.info("Plugin already installed: %s", name)
        return dest

    # Fetch plugin index
    available = fetch_available_plugins()
    plugin_info = None
    for p in available:
        if p["name"] == name:
            plugin_info = p
            break

    if not plugin_info:
        raise FileNotFoundError(
            f"Plugin '{name}' not found in marketplace. "
            f"Available: {[p['name'] for p in available]}"
        )

    # Download plugin
    log.info("Downloading plugin: %s v%s", name, plugin_info["version"])

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / f"{name}.py"
        _download_file(plugin_info["download_url"], tmp_path)

        # Verify checksum — FAIL CLOSED: if verification is requested and the
        # checksum file cannot be fetched or parsed, the install is aborted.
        # Silently skipping verification would let a tampered release through.
        if verify_checksum:
            sha_path = Path(tmpdir) / f"{name}.py.sha256"
            try:
                _download_file(plugin_info["sha256_url"], sha_path)
                expected_sha = sha_path.read_text().strip().split()[0]
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, IndexError) as exc:
                raise RuntimeError(
                    f"Checksum dosyası alınamadı ({name}): {exc}. "
                    f"Doğrulama yapılamadığı için kurulum iptal edildi."
                ) from exc
            actual_sha = _sha256_file(tmp_path)
            if actual_sha.lower() != expected_sha.lower():
                raise RuntimeError(
                    f"Checksum mismatch for {name}: "
                    f"expected {expected_sha}, got {actual_sha}"
                )
            log.info("Checksum verified: %s", name)

        # Install
        shutil.copy2(tmp_path, dest)

    log.info("Plugin installed: %s → %s", name, dest)
    return dest


def uninstall_plugin(name: str) -> bool:
    """Uninstall a locally installed plugin.

    Args:
        name: Plugin name to uninstall.

    Returns:
        True if removed, False if not found.

    Raises:
        ValueError: Plugin name is not a safe identifier.
    """
    _validate_plugin_name(name)
    plugin_path = PLUGIN_DIR / f"{name}.py"
    if plugin_path.exists():
        plugin_path.unlink()
        log.info("Plugin uninstalled: %s", name)
        return True
    return False


def list_installed_plugins() -> list[dict[str, str]]:
    """List locally installed marketplace plugins.

    Returns:
        List of dicts with 'name', 'path', 'size'.
    """
    if not PLUGIN_DIR.exists():
        return []

    plugins = []
    for f in PLUGIN_DIR.glob("*.py"):
        if f.name.startswith("_"):
            continue
        plugins.append({
            "name": f.stem,
            "path": str(f),
            "size": str(f.stat().st_size),
        })
    return sorted(plugins, key=lambda p: p["name"])


def update_plugin(name: str) -> tuple[bool, str, Path | None]:
    """Update an installed plugin to the latest version.

    Checks for newer version, downloads, verifies checksum, and replaces.

    Returns:
        (success, message, plugin_path)
    """
    installed = list_installed_plugins()
    installed_names = {p["name"] for p in installed}

    if name not in installed_names:
        return False, f"Plugin '{name}' kurulu değil", None

    try:
        path = install_plugin(name, force=True)
        return True, f"Plugin güncellendi: {name}", path
    except FileNotFoundError as exc:
        return False, str(exc), None
    except (RuntimeError, ValueError) as exc:
        return False, f"Güncelleme başarısız: {exc}", None


def audit_plugins() -> list[dict[str, str]]:
    """Audit installed plugins for checksum integrity.

    Returns:
        List of dicts with name, status, message for each plugin.
    """
    installed = list_installed_plugins()
    results = []

    for plugin_info in installed:
        name = plugin_info["name"]
        plugin_path = Path(plugin_info["path"])

        try:
            current_hash = _sha256_file(plugin_path)

            # Try to fetch expected hash from marketplace
            available = fetch_available_plugins()
            expected_hash = None
            for p in available:
                if p["name"] == name:
                    try:
                        sha_path = Path(plugin_path.parent) / f"{name}.py.sha256"
                        _download_file(p["sha256_url"], sha_path)
                        expected_hash = sha_path.read_text().strip().split()[0]
                    except Exception as exc:
                        log.debug("SHA256 dosyası indirilemedi: %s", exc)
                    break

            if expected_hash:
                if current_hash == expected_hash:
                    results.append({"name": name, "status": "ok", "message": "Checksum eşleşiyor"})
                else:
                    results.append({"name": name, "status": "changed", "message": f"Hash değişmiş: {current_hash[:16]}... → beklenen: {expected_hash[:16]}..."})
            else:
                results.append({"name": name, "status": "unknown", "message": "Checksum doğrulanamadı (marketplace erişilemez)"})

        except Exception as exc:
            results.append({"name": name, "status": "error", "message": f"Audit hatası: {exc}"})

    return results
