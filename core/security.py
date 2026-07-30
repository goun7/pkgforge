"""PkgForge — Security layer.

Provides file validation, GPG signature checking, path traversal
detection, SHA-256 hashing, and bubblewrap sandbox execution.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

from config import ToolPaths

log = logging.getLogger(__name__)

# Forbidden path components
_TRAVERSAL_PATTERNS = re.compile(r"(^|/)\.\.(/|$)")
_ABSOLUTE_PATH = re.compile(r"^/")

# Valid pacman package name: starts with an alphanumeric or @._+ and contains
# only those plus '-'. Deliberately rejects names starting with '-' (which
# pacman would parse as an option) and any shell/space characters.
_PKG_NAME_RE = re.compile(r"^[a-zA-Z0-9@._+][a-zA-Z0-9@._+-]*$")


def is_valid_package_name(name: str) -> bool:
    """Return True if *name* is a syntactically valid pacman package name.

    Guards against argument injection (e.g. a name like ``-Rns`` or
    ``--dbpath=/tmp``) before the value is ever handed to pacman.
    """
    return bool(name) and len(name) <= 128 and _PKG_NAME_RE.match(name) is not None


# ── File validation ──────────────────────────────────────────────

def validate_mime_type(file_path: Path, tools: ToolPaths) -> str:
    """Return the MIME type of *file_path* using `file --mime-type`.

    Raises ValueError if the file is not a valid .deb or .rpm.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")

    result = subprocess.run(
        [tools.file_cmd, "--mime-type", "-b", str(file_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    mime = result.stdout.strip()
    log.info("MIME type for %s: %s", file_path.name, mime)

    # .deb → application/vnd.debian.binary-package  OR  application/x-debian-package
    # .rpm → application/x-rpm
    valid_mimes = {
        "application/vnd.debian.binary-package",
        "application/x-debian-package",
        "application/x-deb",
        "application/x-rpm",
    }

    if mime not in valid_mimes:
        raise ValueError(
            f"Geçersiz dosya türü: {mime}. "
            f"Yalnızca .deb ve .rpm dosyaları desteklenir."
        )
    return mime


def validate_file_size(file_path: Path, max_mb: int, warn_mb: int) -> str | None:
    """Return a warning string if the file exceeds *warn_mb*, or raise if > *max_mb*."""
    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        raise ValueError(
            f"Dosya boyutu ({size_mb:.0f} MB) maksimum limiti aşıyor ({max_mb} MB)."
        )
    if size_mb > warn_mb:
        return f"Dosya boyutu büyük: {size_mb:.0f} MB"
    return None


# ── Hashing ──────────────────────────────────────────────────────

def sha256_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    digest = h.hexdigest()
    log.info("SHA-256(%s) = %s", file_path.name, digest)
    return digest


# ── GPG signature ────────────────────────────────────────────────

class SignatureResult:
    """Result of a GPG signature verification."""

    __slots__ = ("has_signature", "valid", "signer", "detail")

    def __init__(
        self,
        has_signature: bool = False,
        valid: bool = False,
        signer: str = "",
        detail: str = "",
    ):
        self.has_signature = has_signature
        self.valid = valid
        self.signer = signer
        self.detail = detail


def verify_deb_signature(file_path: Path, tools: ToolPaths) -> SignatureResult:
    """Attempt to verify GPG signature embedded in a .deb archive.

    Most 3rd-party .deb files are unsigned; we just report that fact.
    """
    if not tools.ar or not tools.gpg:
        return SignatureResult(detail="GPG veya ar aracı bulunamadı, imza kontrolü atlandı")

    try:
        # List archive members
        result = subprocess.run(
            [tools.ar, "t", str(file_path)],
            capture_output=True, text=True, timeout=10,
        )
        members = result.stdout.strip().splitlines()

        # Look for _gpg* signature files
        sig_members = [m for m in members if m.startswith("_gpg")]
        if not sig_members:
            return SignatureResult(detail="Paket imzasız (.deb imza dosyası bulunamadı)")

        return SignatureResult(
            has_signature=True,
            detail=f"İmza dosyası bulundu: {', '.join(sig_members)}",
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return SignatureResult(detail=f"İmza kontrolü başarısız: {exc}")


def verify_rpm_signature(file_path: Path, tools: ToolPaths) -> SignatureResult:
    """Attempt basic RPM signature detection via magic bytes."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(96)

        # RPM magic: 0xed 0xab 0xee 0xdb
        if header[:4] != b"\xed\xab\xee\xdb":
            return SignatureResult(detail="Geçersiz RPM magic bytes")

        # Signature tag present if sigtype field is non-zero
        # Byte 6 (sigtype): 0=none, 5=header+payload
        sig_type = header[5] if len(header) > 5 else 0
        if sig_type >= 5:
            return SignatureResult(
                has_signature=True,
                detail="RPM başlığında imza alanı tespit edildi",
            )
        return SignatureResult(detail="RPM imzasız veya imza doğrulanamadı")
    except OSError as exc:
        return SignatureResult(detail=f"RPM imza kontrolü başarısız: {exc}")


# ── Path traversal detection ─────────────────────────────────────

def check_path_traversal(file_list: list[str]) -> list[str]:
    """Check a list of archive member paths for traversal attacks.

    Returns a list of offending paths (empty = safe).
    """
    offending: list[str] = []
    for entry in file_list:
        normalized = str(PurePosixPath(entry))
        if _TRAVERSAL_PATTERNS.search(normalized):
            offending.append(entry)
        elif _ABSOLUTE_PATH.match(entry) and not entry.startswith("./"):
            # Absolute paths inside packages are normal for .deb/.rpm,
            # but we flag those that escape expected prefixes.
            parts = PurePosixPath(entry).parts
            allowed_roots = {"usr", "etc", "opt", "var", "lib", "lib64", "bin", "sbin", "share"}
            if len(parts) > 1 and parts[1] not in allowed_roots:
                offending.append(entry)
    return offending


def check_symlink_attacks(extract_dir: Path) -> list[str]:
    """Walk extracted directory and find symlinks pointing outside the tree."""
    offending: list[str] = []
    extract_resolved = extract_dir.resolve()
    for root, _dirs, files in os.walk(extract_dir):
        for name in files:
            fpath = Path(root) / name
            if fpath.is_symlink():
                target = fpath.resolve()
                if not str(target).startswith(str(extract_resolved)):
                    offending.append(f"{fpath} → {target}")
    return offending


# ── Sandbox execution (bubblewrap) ───────────────────────────────

def build_sandbox_cmd(
    cmd: list[str],
    work_dir: Path,
    tools: ToolPaths,
    *,
    allow_network: bool = False,
    extra_ro_binds: list[Path] | None = None,
) -> tuple[str, list[str]]:
    """Build a (program, args) tuple for running cmd inside bubblewrap sandbox if available."""
    if not tools.bwrap:
        return cmd[0], cmd[1:]

    bwrap_cmd: list[str] = [
        "--unshare-pid",
        "--die-with-parent",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/etc", "/etc",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--symlink", "/usr/lib", "/lib",
        "--symlink", "/usr/lib64", "/lib64",
        "--symlink", "/usr/bin", "/bin",
        "--symlink", "/usr/bin", "/sbin",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",  # nosec B108
        "--bind", str(work_dir), str(work_dir),
    ]

    debtap_cache = Path("/var/cache/debtap")
    if debtap_cache.exists():
        bwrap_cmd += ["--ro-bind", str(debtap_cache), str(debtap_cache)]

    pkgfile_cache = Path("/var/cache/pkgfile")
    if pkgfile_cache.exists():
        bwrap_cmd += ["--ro-bind", str(pkgfile_cache), str(pkgfile_cache)]

    pacman_db = Path("/var/lib/pacman")
    if pacman_db.exists():
        bwrap_cmd += ["--ro-bind", str(pacman_db), str(pacman_db)]

    if extra_ro_binds:
        for bind_path in extra_ro_binds:
            if bind_path.exists():
                bwrap_cmd += ["--ro-bind", str(bind_path), str(bind_path)]

    if not allow_network:
        bwrap_cmd.append("--unshare-net")

    bwrap_cmd += ["--chdir", str(work_dir)]
    bwrap_cmd += cmd

    return tools.bwrap, bwrap_cmd


def run_sandboxed(
    cmd: list[str],
    work_dir: Path,
    tools: ToolPaths,
    *,
    allow_network: bool = False,
    extra_ro_binds: list[Path] | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run *cmd* inside a bubblewrap sandbox.

    Falls back to direct execution if bwrap is unavailable.
    """
    program, args = build_sandbox_cmd(
        cmd, work_dir, tools, allow_network=allow_network, extra_ro_binds=extra_ro_binds
    )
    if program == tools.bwrap:
        log.info("Sandbox cmd: %s %s ...", program, " ".join(args[:8]))
        return subprocess.run([program] + args, capture_output=True, text=True, timeout=timeout)
    else:
        log.warning("bubblewrap bulunamadı, sandbox'sız çalıştırılıyor")
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(work_dir), timeout=timeout)



# ── Command injection prevention ─────────────────────────────────

def safe_run(
    cmd: list[str],
    *,
    cwd: str | Path | None = None,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command with shell=False (no injection) and a timeout."""
    log.debug("Executing: %s", cmd)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        timeout=timeout,
        env=env,
    )
