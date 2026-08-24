"""Faz 5 (F5.18) — fleet sync backend soyutlamasi + age sifreleme.

Backend secimi (webdav | git | rclone-s3) bir fabrika uzerinden yapilir; her
backend kendi Aracinin kurulu olup olmadigini denetler ve yoksa net bir
SyncError firlatir. age CLI kuruluysa uctan uca sifreleme saglanir; anahtarlik
entegrasyonu hazirdir (sifreleme anahtari keyring'de tutulabilir).
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

BACKENDS = ("webdav", "git", "rclone-s3")
_AGE_TIMEOUT_S = 30


class SyncBackendError(RuntimeError):
    """Backend kaynakli senkron hatasi."""


# --- age sifreleme --------------------------------------------------------

def age_available() -> bool:
    return shutil.which("age") is not None


def age_encrypt(blob: bytes, recipient: str) -> bytes:
    """Encrypt a blob with an age recipient public key (best-effort)."""
    if not age_available():
        raise SyncBackendError("age CLI kurulu degil (pacman -S age)")
    if not recipient:
        raise SyncBackendError("age alici anahtari (recipient) bos")
    res = subprocess.run(
        ["age", "-r", recipient, "-a"],
        input=blob, capture_output=True, timeout=_AGE_TIMEOUT_S, check=False)
    if res.returncode != 0:
        raise SyncBackendError(f"age sifreleme basarisiz: {res.stderr[:200]!r}")
    return res.stdout


def age_decrypt(blob: bytes, identity_path: str | Path) -> bytes:
    """Decrypt an age blob using an identity (private key) file."""
    if not age_available():
        raise SyncBackendError("age CLI kurulu degil (pacman -S age)")
    ident = Path(identity_path)
    if not ident.is_file():
        raise SyncBackendError(f"age identity dosyasi yok: {ident}")
    res = subprocess.run(
        ["age", "-d", "-i", str(ident)],
        input=blob, capture_output=True, timeout=_AGE_TIMEOUT_S, check=False)
    if res.returncode != 0:
        raise SyncBackendError(f"age cozme basarisiz: {res.stderr[:200]!r}")
    return res.stdout


# --- backend soyutlamasi --------------------------------------------------

class SyncBackend:
    """Abstract sync backend; subclasses implement push/pull."""

    name = "base"

    def is_available(self) -> bool:
        return False

    def push(self, blob: bytes, remote_name: str) -> dict:
        raise NotImplementedError

    def pull(self, remote_name: str) -> bytes:
        raise NotImplementedError


class GitBackend(SyncBackend):
    """Sync a bundle blob through a git repository."""

    name = "git"

    def __init__(self, repo_url: str, branch: str = "main"):
        self.repo_url = repo_url
        self.branch = branch

    def is_available(self) -> bool:
        return shutil.which("git") is not None and bool(self.repo_url)

    def push(self, blob: bytes, remote_name: str) -> dict:
        if not self.is_available():
            raise SyncBackendError("git kurulu degil ya da repo_url bos")
        import tempfile

        with tempfile.TemporaryDirectory(prefix="pkgforge_gitsync_") as td:
            repo = Path(td) / "repo"
            _run(["git", "clone", "--depth=1", "-b", self.branch,
                  self.repo_url, str(repo)])
            (repo / remote_name).write_bytes(blob)
            _run(["git", "-C", str(repo), "add", remote_name])
            _run(["git", "-C", str(repo), "-c", "user.email=sync@pkgforge.app",
                  "-c", "user.name=PkgForge Sync",
                  "commit", "-m", f"sync {remote_name}"])
            _run(["git", "-C", str(repo), "push", "origin", self.branch])
        return {"ok": True, "backend": "git", "size": len(blob)}

    def pull(self, remote_name: str) -> bytes:
        if not self.is_available():
            raise SyncBackendError("git kurulu degil ya da repo_url bos")
        import tempfile

        with tempfile.TemporaryDirectory(prefix="pkgforge_gitsync_") as td:
            repo = Path(td) / "repo"
            _run(["git", "clone", "--depth=1", "-b", self.branch,
                  self.repo_url, str(repo)])
            target = repo / remote_name
            if not target.is_file():
                raise SyncBackendError(f"Uzak dosya yok: {remote_name}")
            return target.read_bytes()


class RcloneBackend(SyncBackend):
    """Sync a bundle blob via rclone (S3 ve diger uzak depolar)."""

    name = "rclone-s3"

    def __init__(self, remote: str):
        # remote ornek: "s3:bucket/prefix"
        self.remote = remote.rstrip("/")

    def is_available(self) -> bool:
        return shutil.which("rclone") is not None and bool(self.remote)

    def push(self, blob: bytes, remote_name: str) -> dict:
        if not self.is_available():
            raise SyncBackendError("rclone kurulu degil ya da remote bos")
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(blob)
            tmp_path = tmp.name
        try:
            _run(["rclone", "copyto", tmp_path,
                  f"{self.remote}/{remote_name}"])
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return {"ok": True, "backend": "rclone-s3", "size": len(blob)}

    def pull(self, remote_name: str) -> bytes:
        if not self.is_available():
            raise SyncBackendError("rclone kurulu degil ya da remote bos")
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _run(["rclone", "copyto",
                  f"{self.remote}/{remote_name}", tmp_path])
            return Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)


def _run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True,
                         timeout=120, check=False)
    if res.returncode != 0:
        raise SyncBackendError(
            f"{' '.join(cmd[:3])} basarisiz: {res.stderr[:200]!r}")


def get_backend(name: str, **cfg) -> SyncBackend:
    """Factory: return a backend instance by name."""
    name = (name or "").lower().strip()
    if name == "git":
        return GitBackend(cfg.get("repo_url", ""), cfg.get("branch", "main"))
    if name == "rclone-s3":
        return RcloneBackend(cfg.get("remote", ""))
    if name == "webdav":
        # WebDAV mevcut cloud_sync icinde yonetilir; burada bir temsilci doner.
        raise SyncBackendError(
            "webdav backend'i core.cloud_sync.webdav_push/pull ile kullanilir")
    raise SyncBackendError(f"Bilinmeyen backend: {name} ({' | '.join(BACKENDS)})")
