"""PkgForge — Backup bundles & optional WebDAV cloud sync (C3).

Backup bundles are plain zip archives holding every profile's settings.json
and history.db (plus SQLite WAL sidecars when present), so a restore covers
multi-profile state. Remote sync targets any WebDAV server using only the
standard library (urllib) — no extra dependencies; misconfiguration degrades
to a clear error instead of crashing.
"""

from __future__ import annotations

import base64
import json
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

import config
from config import APP_VERSION, PROFILE_NAME_RE

# Per-profile files captured in every bundle.
_BUNDLE_FILES = ("settings.json", "history.db", "history.db-wal", "history.db-shm")

# Marker entry identifying a genuine PkgForge bundle.
_MARKER = "pkgforge-backup.json"

_REMOTE_NAME = "pkgforge-backup.zip"


class SyncError(RuntimeError):
    """Raised for backup/sync failures with a user-facing message."""


def _net_reason(exc: BaseException) -> object:
    """Best-effort reason extraction across URLError/OSError/TimeoutError."""
    return getattr(exc, "reason", None) or exc


def _profile_names() -> list[str]:
    names = [config.DEFAULT_PROFILE]
    root = config.profiles_dir()
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and PROFILE_NAME_RE.match(entry.name):
                names.append(entry.name)
    return names


def export_backup(output_path: str | None = None) -> dict:
    """Bundle all profiles' settings/history into one zip archive."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if output_path:
        out = Path(output_path).expanduser()
    else:
        out = config.backup_dir() / f"pkgforge-backup-{stamp}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    included = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in _profile_names():
            src_dir = config.profile_config_dir(name)
            for fname in _BUNDLE_FILES:
                f = src_dir / fname
                if f.is_file():
                    zf.write(f, arcname=f"{name}/{fname}")
                    included += 1
        zf.writestr(_MARKER, json.dumps({
            "app": "PkgForge",
            "version": APP_VERSION,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "profiles": _profile_names(),
            "files": included,
        }))
    if included == 0:
        out.unlink(missing_ok=True)
        raise SyncError("Yedeklenecek ayar/geçmiş bulunamadı")
    return {"ok": True, "path": str(out), "size": out.stat().st_size}


def import_backup(backup_path: str) -> dict:
    """Restore a PkgForge backup bundle into the current config root."""
    p = Path(backup_path).expanduser()
    if not p.is_file():
        raise SyncError(f"Yedek dosyası bulunamadı: {p}")

    restored: list[str] = []
    with zipfile.ZipFile(p) as zf:
        names = zf.namelist()
        if _MARKER not in names:
            raise SyncError("Geçersiz PkgForge yedeği (imza eksik)")

        # Replace DBs atomically enough: drop stale WAL sidecars of any
        # database being restored before writing the new main file.
        planned: dict[tuple[str, str], bytes] = {}
        for member in names:
            if member == _MARKER:
                continue
            parts = PurePosixPath(member).parts
            if len(parts) != 2:
                raise SyncError(f"Güvenilmeyen arşiv üyesi: {member}")
            profile, fname = parts
            if not PROFILE_NAME_RE.match(profile) or fname not in _BUNDLE_FILES:
                raise SyncError(f"Güvenilmeyen arşiv üyesi: {member}")
            planned[(profile, fname)] = zf.read(member)

        for (profile, fname), blob in planned.items():
            target = config.profile_config_dir(profile) / fname
            target.parent.mkdir(parents=True, exist_ok=True)
            if fname == "history.db":
                for side in ("history.db-wal", "history.db-shm"):
                    if (profile, side) not in planned:
                        (target.parent / side).unlink(missing_ok=True)
            target.write_bytes(blob)
            restored.append(f"{profile}/{fname}")

    return {"ok": True, "restored": restored}


def _webdav_target() -> tuple[str, dict[str, str]]:
    s = __import__("i18n").load_settings()
    url = str(s.get("sync_url", "")).strip()
    if not url:
        raise SyncError("Senkron sunucusu yapılandırılmadı (Ayarlar › Bulut Senkronizasyonu)")
    if url.lower().startswith("http://") and not s.get("allow_insecure_http"):
        raise SyncError(
            "http:// adresine izin verilmiyor — https:// kullanın veya "
            "Ayarlar'dan 'Güvensiz HTTP'ye izin ver'i açın"
        )
    if not url.endswith("/"):
        url += "/"
    headers = {"Content-Type": "application/zip"}
    user = str(s.get("sync_username", ""))
    pw = str(s.get("sync_password", ""))
    if user or pw:
        token = base64.b64encode(f"{user}:{pw}".encode()).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return url, headers


def webdav_push() -> dict:
    """Upload a fresh backup bundle to the configured WebDAV server."""
    url, headers = _webdav_target()
    bundle_path = export_backup()["path"]
    blob = Path(bundle_path).read_bytes()
    req = urllib.request.Request(url + _REMOTE_NAME, data=blob,
                                 method="PUT", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        raise SyncError(f"Sunucu hatası: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SyncError(f"Sunucuya ulaşılamadı: {_net_reason(exc)}") from exc
    return {"ok": True, "remote": url + _REMOTE_NAME, "size": len(blob)}


def webdav_pull() -> dict:
    """Download the remote bundle and restore it over local state."""
    url, headers = _webdav_target()
    req = urllib.request.Request(url + _REMOTE_NAME, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            blob = resp.read()
    except urllib.error.HTTPError as exc:
        raise SyncError(f"Sunucu hatası: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SyncError(f"Sunucuya ulaşılamadı: {_net_reason(exc)}") from exc

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(blob)
        tmp_path = tmp.name
    try:
        result = import_backup(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return result
