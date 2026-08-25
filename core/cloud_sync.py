"""PkgForge — Backup bundles & optional WebDAV cloud sync (C3).

Backup bundles are plain zip archives holding every profile's settings.json
and history.db (plus SQLite WAL sidecars when present), so a restore covers
multi-profile state. Remote sync targets any WebDAV server using only the
standard library (urllib) — no extra dependencies; misconfiguration degrades
to a clear error instead of crashing.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
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
_MANIFEST = "manifest.json"

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

    # Checkpoint SQLite WAL so the bundled .db is complete without sidecars.
    for name in _profile_names():
        db = config.history_db_path(name)
        if db.is_file():
            try:
                with sqlite3.connect(db) as conn:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass  # busy/corrupt db: bundle whatever is readable

    hashes: dict[str, str] = {}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in _profile_names():
            src_dir = config.profile_config_dir(name)
            for fname in _BUNDLE_FILES:
                f = src_dir / fname
                if f.is_file():
                    arc = f"{name}/{fname}"
                    zf.write(f, arcname=arc)
                    hashes[arc] = hashlib.sha256(f.read_bytes()).hexdigest()
        zf.writestr(_MANIFEST, json.dumps({
            "files": hashes,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        }))
        zf.writestr(_MARKER, json.dumps({
            "app": "PkgForge",
            "version": APP_VERSION,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "profiles": _profile_names(),
            "files": len(hashes),
        }))
    if not hashes:
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
        if _MARKER not in names or _MANIFEST not in names:
            raise SyncError("Geçersiz PkgForge yedeği (imza/manifest eksik)")
        expected: dict[str, str] = json.loads(zf.read(_MANIFEST)).get("files", {})

        # Replace DBs atomically: verify every hash first, drop stale WAL
        # sidecars of any database being restored, then os.replace each file.
        planned: dict[tuple[str, str], bytes] = {}
        for member in names:
            if member in (_MARKER, _MANIFEST):
                continue
            parts = PurePosixPath(member).parts
            if len(parts) != 2:
                raise SyncError(f"Güvenilmeyen arşiv üyesi: {member}")
            profile, fname = parts
            if not PROFILE_NAME_RE.match(profile) or fname not in _BUNDLE_FILES:
                raise SyncError(f"Güvenilmeyen arşiv üyesi: {member}")
            blob = zf.read(member)
            want = expected.get(member)
            if want and hashlib.sha256(blob).hexdigest() != want:
                raise SyncError(f"Bütünlük hatası: {member}")
            planned[(profile, fname)] = blob

        for (profile, fname), blob in planned.items():
            target = config.profile_config_dir(profile) / fname
            target.parent.mkdir(parents=True, exist_ok=True)
            if fname == "history.db":
                for side in ("history.db-wal", "history.db-shm"):
                    if (profile, side) not in planned:
                        (target.parent / side).unlink(missing_ok=True)
            tmp_target = target.with_suffix(target.suffix + ".tmp")
            tmp_target.write_bytes(blob)
            os.replace(tmp_target, target)
            restored.append(f"{profile}/{fname}")

    return {"ok": True, "restored": restored}


def restore_drill() -> dict:
    """F5.17: export -> izole import -> hash dogrulama tatbikati.

    Gercek yapilandirmaya dokunmadan yedek/geri-yukleme yolunun uctan uca
    calistigini kanitlar: mevcut profilleri gecici bir pakete export eder,
    config kokunu tek kullanimlik bir dizine yonlendirip oraya import eder
    (import_backup her uyenin sha256'sini manifest'e karsi zaten dogrular),
    sonra geri yuklenen dosyalarin diskte varligini sayar ve temizlenir.
    """
    import shutil
    import tempfile

    workdir = Path(tempfile.mkdtemp(prefix="pkgforge-drill-"))
    bundle = workdir / "drill-backup.zip"
    restore_root = workdir / "restore"
    original_root = config.CONFIG_DIR
    try:
        try:
            exp = export_backup(output_path=str(bundle))
        except SyncError as exc:
            # Bos yapilandirma: tatbikat edecek veri yok, mekanik saglikli.
            return {"ok": True, "detail": f"tatbikat atlandi: {exc}"}
        if exp.get("ok") is False or not bundle.is_file():
            return {"ok": False, "detail": "export basarisiz: " + str(exp)}

        with zipfile.ZipFile(bundle) as zf:
            if _MANIFEST not in zf.namelist():
                return {"ok": False, "detail": "manifest eksik"}
            expected = json.loads(zf.read(_MANIFEST)).get("files", {})

        config.CONFIG_DIR = restore_root
        try:
            imp = import_backup(str(bundle))
        finally:
            config.CONFIG_DIR = original_root
        if not imp.get("ok"):
            return {"ok": False, "detail": "import basarisiz: " + str(imp)}

        restored = imp.get("restored", [])
        missing = []
        for arc in restored:
            profile, _, fname = arc.partition("/")
            target = (restore_root if profile == "default"
                      else restore_root / "profiles" / profile) / fname
            if not target.is_file():
                missing.append(arc)
        if missing:
            return {"ok": False,
                    "detail": "eksik geri yuklenen dosya: " + ", ".join(missing)}
        return {"ok": True,
                "detail": (f"tatbikat basarili: {len(restored)}/{len(expected)}"
                           f" dosya dogrulandi")}
    except SyncError as exc:
        return {"ok": False, "detail": str(exc)}
    finally:
        config.CONFIG_DIR = original_root
        shutil.rmtree(workdir, ignore_errors=True)


def _webdav_target() -> tuple[str, dict[str, str]]:
    s = __import__("i18n").load_settings()
    url = str(s.get("sync_url", "")).strip()
    if not url:
        raise SyncError("Senkron sunucusu yapılandırılmadı (Ayarlar › Bulut Senkronizasyonu)")
    low = url.lower()
    if low.startswith("http://") and not s.get("allow_insecure_http"):
        raise SyncError(
            "http:// adresine izin verilmiyor — https:// kullanın veya "
            "Ayarlar'dan 'Güvensiz HTTP'ye izin ver'i açın"
        )
    if not low.startswith(("http://", "https://")):
        # SEC: file:///ftp:/data: gibi semalar urlopen ile yerel dosya okuma
        # veya beklenmedik protokol erişimine yol açabilir; beyaz liste dışı
        # her şema reddedilir.
        raise SyncError(
            "Desteklenmeyen adres şeması — yalnızca https:// "
            "(veya açık onayla http://) kullanılabilir"
        )
    if not url.endswith("/"):
        url += "/"
    headers = {"Content-Type": "application/zip"}
    user = str(s.get("sync_username", ""))
    # F4.4: prefer the OS keyring; plaintext settings value is a legacy
    # fallback that sync.config removes once the keyring accepts a secret.
    pw = ""
    try:
        from core.secrets_store import available, webdav_store

        if user and available():
            stored = webdav_store(user).get_secret()
            if stored is not None:
                pw = stored
    except Exception as exc:  # noqa: BLE001 - never break push over keyring
        __import__("logging").getLogger(__name__).debug(
            "keyring lookup failed: %s", exc)
    if not pw:
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
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 - sem beyaz listesi _webdav_target'ta uygulanır
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
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 - sem beyaz listesi _webdav_target'ta uygulanır
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
