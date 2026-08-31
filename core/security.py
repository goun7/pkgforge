"""PkgForge — Security layer.

Provides file validation, GPG signature checking, path traversal
detection, SHA-256 hashing, and bubblewrap sandbox execution.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import stat
import subprocess
from pathlib import Path, PurePosixPath

from config import ToolPaths
from i18n import tr

log = logging.getLogger(__name__)

__all__ = [
    "SignatureResult",
    "build_sandbox_cmd",
    "check_compression_bomb",
    "check_dangerous_files",
    "check_path_traversal",
    "check_symlink_attacks",
    "is_valid_package_name",
    "run_sandboxed",
    "safe_run",
    "sha256_hash",
    "validate_file_size",
    "validate_mime_type",
    "verify_deb_signature",
    "verify_rpm_signature",
]

# Forbidden path components
_TRAVERSAL_PATTERNS = re.compile(r"(^|/)\.\.(/|$)")
_ABSOLUTE_PATH = re.compile(r"^/")

# Standard FHS roots that packages legitimately own. Single source of truth:
# check_path_traversal() allows these as absolute member roots, and
# check_symlink_attacks() derives its absolute-target whitelist from them, so
# the two lists can never drift apart.
_FHS_ROOTS = (
    "usr", "etc", "opt", "var", "bin", "sbin",
    "lib", "lib32", "lib64", "share", "run",
)

# Absolute prefixes derived from _FHS_ROOTS: a symlink target under one of
# these is interpreted *relative to the package root* at install time (e.g.
# /usr/bin/app -> /usr/share/app/bin/app), so it stays inside the package.
# Anything else (e.g. /home, /root, /tmp, /proc, /sys) is an escape to
# host-private storage.
_SAFE_ABSOLUTE_PREFIXES = tuple("/" + root for root in _FHS_ROOTS)

# High-signal indicators looked for inside ELF binaries during the package
# security scan. Purely heuristic and non-fatal (warnings only).
_ELF_SUSPICIOUS_PATTERNS = (
    b"/bin/sh -i",
    b"/bin/bash -i",
    b"nc -e ",
    b"ncat -e ",
    b"-e /bin/sh",
    b"LD_PRELOAD",
    b"socat exec:",
)

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
        check=False,
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
        "application/x-archive",  # some DEBs detected as generic ar archive
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


# ── Decompression bomb detection ─────────────────────────────────

# Maximum allowed compression ratio before flagging as potential bomb.
# Real-world DEBs rarely exceed 10x; zip bombs are typically > 100x.
_MAX_COMPRESSION_RATIO = 50

def check_compression_bomb(
    archive_path: Path,
    tools: ToolPaths,
    *,
    max_ratio: int = _MAX_COMPRESSION_RATIO,
) -> str | None:
    """Check if a DEB/RPM archive is a potential decompression bomb.

    Uses ``file`` and ``bsdtar`` to estimate the uncompressed size of the
    archive's data payload.  Returns a warning string if the compression
    ratio exceeds *max_ratio*, or None if the archive appears safe.
    """
    if not archive_path.is_file():
        return None

    archive_mb = archive_path.stat().st_size / (1024 * 1024)
    if archive_mb < 0.1:
        return None  # Too small to be a bomb

    try:
        # For DEBs: list data.tar.* members and sum their uncompressed sizes
        suffix = archive_path.suffix.lower()
        if suffix == ".deb" and tools.ar and tools.bsdtar:
            ar_res = safe_run([tools.ar, "t", str(archive_path)], timeout=10)
            if ar_res.returncode != 0:
                return None

            data_tar = None
            for m in ar_res.stdout.strip().splitlines():
                if m.strip().startswith("data.tar"):
                    data_tar = m.strip()
                    break
            if not data_tar:
                return None

            # Extract data.tar and list contents with sizes
            ar_p = safe_run([tools.ar, "p", str(archive_path), data_tar], timeout=30)
            if ar_p.returncode != 0:
                return None

            # Use bsdtar to get file list — estimate uncompressed from member count
            tar_list = safe_run(
                [tools.bsdtar, "-tzf", "-"] if data_tar.endswith(".gz")
                else [tools.bsdtar, "-tf", "-"],
                input=ar_p.stdout,
                timeout=30,
            )
            if tar_list.returncode != 0:
                return None

            member_count = len(tar_list.stdout.strip().splitlines())
            if member_count < 10:
                return None

            # Heuristic: if archive is small but has many members, suspect bomb
            # Also check for suspiciously large individual members
            estimated_mb = member_count * 0.01  # rough estimate
            if archive_mb > 0 and estimated_mb / archive_mb > max_ratio:
                return (
                    f"⚠ Potansiyel decompression bomb: {member_count} dosya, "
                    f"tahmini sıkıştırma oranı > {max_ratio}x"
                )

        # For RPMs: similar check using rpm2cpio header
        elif suffix == ".rpm" and tools.rpm2cpio:
            # RPM header contains installed_size — compare with file size
            rpm_info = safe_run(
                [tools.rpm2cpio, "-qp", "--queryformat", "%{SIZE}\n%{PAYLOADSIZE}\n",
                 str(archive_path)],
                timeout=10,
            )
            if rpm_info.returncode == 0:
                lines = rpm_info.stdout.strip().splitlines()
                if len(lines) >= 2:
                    try:
                        installed_kb = int(lines[0]) // 1024
                        payload_kb = int(lines[1]) // 1024
                        # Compare uncompressed (KB) vs compressed (MB) in same units
                        if payload_kb > 0 and installed_kb / (archive_mb * 1024) > max_ratio:
                            return (
                                f"⚠ Potansiyel decompression bomb: "
                                f"kurulum boyutu {installed_kb}KB, arşiv {archive_mb:.0f}MB"
                            )
                    except (ValueError, IndexError):
                        pass

    except Exception as exc:  # noqa: BLE001
        log.debug(tr("security.decompression_bomb_kontrolu_basarisiz_s"), exc)

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

    __slots__ = ("detail", "has_signature", "signer", "valid")

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
            capture_output=True, text=True, timeout=10, check=False,
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
            # but we flag those that escape expected FHS prefixes.
            parts = PurePosixPath(entry).parts
            if len(parts) > 1 and parts[1] not in _FHS_ROOTS:
                offending.append(entry)
    return offending


def _safe_resolve(path: Path) -> Path:
    """Resolve *path* without raising on missing targets or symlink loops.

    ``Path.resolve`` raises on non-existent paths under Python 3.13+ (where
    ``strict`` defaults to True) and on symlink loops; package contents are
    exactly the kind of untrusted input where those failures are common, so
    resolution must never crash the security scan. Falls back to a purely
    lexical normalization when the filesystem cannot be traversed.
    """
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError):
        # Last resort: normalize lexically (collapses ../ and //) without
        # touching the filesystem, which is enough for containment checks.
        return Path(os.path.normpath(path))


def check_symlink_attacks(extract_dir: Path) -> list[str]:
    """Walk extracted directory and find symlinks escaping the package root.

    Absolute symlinks such as ``/usr/bin/app -> /usr/share/app/bin/app`` are a
    standard, legitimate packaging pattern (FHS layout): the target resolves
    inside the package when installed. Only symlinks that escape into
    host-private locations (``/home``, ``/root``, ``/tmp``, ``/proc`` ...) or
    that use relative ``..`` escapes are flagged. Directory symlinks are
    checked as well as file symlinks.
    """
    offending: list[str] = []
    extract_resolved = _safe_resolve(extract_dir)
    prefix = str(extract_resolved)
    for root, dirs, files in os.walk(extract_dir):
        for name in dirs + files:
            fpath = Path(root) / name
            if not fpath.is_symlink():
                continue
            raw_target = os.readlink(fpath)
            if os.path.isabs(raw_target):
                # Normalize so crafted targets like "/usr/share/../../etc/passwd"
                # cannot slip past the prefix check.
                normalized = os.path.normpath(raw_target)
                # 1) FHS-style targets (e.g. /usr/share/app/bin/app) are interpreted
                #    relative to the package root at install time → safe.
                fhs_safe = any(
                    normalized == p or normalized.startswith(p + "/")
                    for p in _SAFE_ABSOLUTE_PREFIXES
                )
                # 2) Target interpreted relative to the extraction root and really
                #    present inside it (another file shipped by the package).
                in_tree = extract_resolved / normalized.lstrip("/")
                inside = (
                    str(in_tree) == prefix or str(in_tree).startswith(prefix + os.sep)
                ) and in_tree.exists()
                # 3) Target resolves on this host to a path inside the tree
                #    (e.g. an absolute link to another extracted file).
                host_resolved = _safe_resolve(Path(raw_target))
                host_inside = (
                    str(host_resolved) == prefix
                    or str(host_resolved).startswith(prefix + os.sep)
                )
                if not (fhs_safe or inside or host_inside):
                    offending.append(f"{fpath} → {raw_target}")
            else:
                resolved = _safe_resolve(fpath.parent / raw_target)
                if not (
                    str(resolved) == prefix
                    or str(resolved).startswith(prefix + os.sep)
                ):
                    offending.append(f"{fpath} → {raw_target}")
    return offending


# ── Dangerous file scan (setuid / devices / suspicious ELF) ──────

def check_dangerous_files(
    extract_dir: Path, *, max_elf_scan: int = 100, elf_scan_bytes: int = 1 << 20
) -> tuple[list[str], list[str]]:
    """Scan extracted tree for dangerous file properties.

    Returns ``(errors, warnings)`` where:

    * **errors** – device/socket/FIFO nodes. Almost never legitimate inside an
      application package; block conversion.
    * **warnings** – setuid/setgid binaries, world-writable files/dirs and ELF
      binaries whose first 1 MiB contains reverse-shell / preload indicators.
      Informational; conversion may continue. Setuid is deliberately *not* a
      hard error because Electron apps legitimately ship ``chrome-sandbox``
      (mode 4755) — blocking on it would break the tool's main use case.

    Symlinks are not followed. Scanning is bounded (``max_elf_scan`` binaries,
    ``elf_scan_bytes`` per file) so a huge package cannot stall the pipeline.
    """
    errors: list[str] = []
    warnings: list[str] = []
    elfs_checked = 0

    for root, dirs, files in os.walk(extract_dir):
        for name in dirs + files:
            fpath = Path(root) / name
            try:
                st = fpath.lstat()
            except OSError:
                continue

            rel = fpath.relative_to(extract_dir)
            if stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode):
                perms = stat.S_IMODE(st.st_mode)
                if perms & (stat.S_ISUID | stat.S_ISGID):
                    warnings.append(f"setuid/setgid: {rel} (mode {oct(perms)})")
                elif perms & 0o002:
                    warnings.append(f"world-writable: {rel}")

                # Only probe for the ELF magic while we still have scan budget,
                # so huge trees do not open every single file.
                if (
                    stat.S_ISREG(st.st_mode)
                    and elfs_checked < max_elf_scan
                    and _looks_like_elf(fpath)
                ):
                    elfs_checked += 1
                    if _elf_has_suspicious_pattern(fpath, elf_scan_bytes):
                        warnings.append(f"suspicious-elf: {rel}")
            elif (
                stat.S_ISFIFO(st.st_mode)
                or stat.S_ISSOCK(st.st_mode)
                or stat.S_ISCHR(st.st_mode)
                or stat.S_ISBLK(st.st_mode)
            ):
                errors.append(f"device/fifo/socket node: {rel}")

    return errors, warnings


def _looks_like_elf(fpath: Path) -> bool:
    """Return True if *fpath* starts with the ELF magic bytes (no execution)."""
    try:
        with open(fpath, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


def _elf_has_suspicious_pattern(fpath: Path, max_bytes: int) -> bool:
    """Scan the first *max_bytes* of an ELF binary for attack indicators."""
    try:
        with open(fpath, "rb") as f:
            blob = f.read(max_bytes)
    except OSError:
        return False
    return any(pattern in blob for pattern in _ELF_SUSPICIOUS_PATTERNS)


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
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",  # nosec B108
        "--bind", str(work_dir), str(work_dir),
    ]

    # Replicate the host FHS layout inside the sandbox. On Arch /bin, /sbin,
    # /lib, /lib64 are symlinks into /usr; on other distros they are real
    # directories. Mirror whatever the host does — binding a directory and then
    # trying to symlink over it (or vice versa) makes bwrap fail with
    # "destination exists and is not a symlink".
    for merged_dir in ("/bin", "/sbin", "/lib", "/lib64"):
        if os.path.islink(merged_dir):
            target = os.path.realpath(merged_dir)
            if target.startswith("/usr/"):
                bwrap_cmd += ["--symlink", target, merged_dir]
            else:
                bwrap_cmd += ["--ro-bind", merged_dir, merged_dir]
        elif os.path.isdir(merged_dir):
            bwrap_cmd += ["--ro-bind", merged_dir, merged_dir]

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
        return subprocess.run([program] + args, capture_output=True, text=True, timeout=timeout, check=False)
    else:
        log.warning(tr("security.bubblewrap_bulunamadi_sandbox_siz_calist"))
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(work_dir), timeout=timeout, check=False)



# ── Command injection prevention ─────────────────────────────────

def safe_run(
    cmd: list[str],
    *,
    cwd: str | Path | None = None,
    timeout: int = 120,
    env: dict[str, str] | None = None,
    input: str | bytes | None = None,
    text: bool | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command with shell=False (no injection) and a timeout.

    Args:
        text: If None (default), auto-detect from input type.
              If True, force text mode (stdout/stderr are str).
              If False, force binary mode (stdout/stderr are bytes).
    """
    log.debug("Executing: %s", cmd)
    if text is None:
        use_text = not isinstance(input, bytes)
    else:
        use_text = text
    return subprocess.run(
        cmd,
        capture_output=True,
        text=use_text,
        cwd=str(cwd) if cwd else None,
        timeout=timeout,
        env=env,
        input=input,
        check=False,
    )
