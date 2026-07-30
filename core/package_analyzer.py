"""PkgForge — Package analyzer.

Extracts metadata from .deb and .rpm files, checks architecture
compatibility, detects existing installations, and identifies
potential file conflicts.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from config import (
    DEB_ARCH_MAP,
    RPM_ARCH_MAP,
    SUPPORTED_ARCHES,
    ToolPaths,
)
from core.security import safe_run

log = logging.getLogger(__name__)

PackageType = Literal["deb", "rpm"]


@dataclass
class PackageMetadata:
    """Parsed metadata from a .deb or .rpm file."""

    file_path: Path = Path()
    package_type: PackageType = "deb"
    name: str = ""
    version: str = ""
    arch: str = ""           # Original arch string (e.g., "amd64")
    arch_mapped: str = ""    # Arch Linux equivalent (e.g., "x86_64")
    description: str = ""
    maintainer: str = ""
    url: str = ""
    depends: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    installed_size_kb: int = 0
    file_list: list[str] = field(default_factory=list)

    # Existing installation info
    already_installed: bool = False
    installed_version: str = ""

    @property
    def arch_compatible(self) -> bool:
        return self.arch_mapped in SUPPORTED_ARCHES


def analyze_package(file_path: Path, tools: ToolPaths) -> PackageMetadata:
    """Determine package type and extract metadata."""
    suffix = file_path.suffix.lower()

    if suffix == ".deb":
        return _analyze_deb(file_path, tools)
    elif suffix == ".rpm":
        return _analyze_rpm(file_path, tools)
    else:
        raise ValueError(f"Desteklenmeyen dosya uzantısı: {suffix}")


# ── .deb analysis ────────────────────────────────────────────────

def _analyze_deb(file_path: Path, tools: ToolPaths) -> PackageMetadata:
    """Extract metadata from a Debian package using ar + tar."""
    meta = PackageMetadata(file_path=file_path, package_type="deb")

    if not tools.ar:
        raise RuntimeError("'ar' aracı bulunamadı — binutils paketi gerekli")

    # List archive members to find control.tar.*
    ar_result = safe_run([tools.ar, "t", str(file_path)])
    if ar_result.returncode != 0:
        raise RuntimeError(f"ar başarısız: {ar_result.stderr}")

    members = ar_result.stdout.strip().splitlines()
    control_tar = None
    for m in members:
        if m.startswith("control.tar"):
            control_tar = m
            break
    if not control_tar:
        raise RuntimeError(".deb arşivinde control.tar bulunamadı")

    # Extract control file content
    # ar p <file> control.tar.* | tar -xO ./control  (or just control)
    extract_result = subprocess.run(
        [tools.ar, "p", str(file_path), control_tar],
        capture_output=True,
        timeout=30,
    )
    if extract_result.returncode != 0:
        raise RuntimeError(f"control.tar çıkarılamadı: {extract_result.stderr}")

    # Determine tar flags for decompression
    tar_flags = _tar_flags_for(control_tar)
    tar_result = subprocess.run(
        [tools.bsdtar, "-xf", "-", "--to-stdout", "./control"] if tools.bsdtar
        else ["tar", f"-x{tar_flags}f", "-", "--to-stdout", "./control"],
        input=extract_result.stdout,
        capture_output=True,
        timeout=30,
    )

    # Fallback: try without ./ prefix
    if tar_result.returncode != 0:
        tar_result = subprocess.run(
            [tools.bsdtar, "-xf", "-", "--to-stdout", "control"] if tools.bsdtar
            else ["tar", f"-x{tar_flags}f", "-", "--to-stdout", "control"],
            input=extract_result.stdout,
            capture_output=True,
            timeout=30,
        )

    if tar_result.returncode != 0:
        raise RuntimeError(f"control dosyası okunamadı: {tar_result.stderr}")

    control_text = tar_result.stdout.decode("utf-8", errors="replace")
    _parse_deb_control(control_text, meta)

    # Map architecture
    meta.arch_mapped = DEB_ARCH_MAP.get(meta.arch, meta.arch)

    # Extract file list from data.tar.*
    data_tar = None
    for m in members:
        if m.startswith("data.tar"):
            data_tar = m
            break
    if data_tar:
        _extract_deb_file_list(file_path, data_tar, meta, tools)

    # Check existing installation
    _check_installed(meta, tools)

    log.info("DEB analizi tamamlandı: %s %s (%s)", meta.name, meta.version, meta.arch_mapped)
    return meta


def _parse_deb_control(text: str, meta: PackageMetadata) -> None:
    """Parse Debian control file fields."""
    current_key = ""
    current_value = ""

    for line in text.splitlines():
        if line.startswith(" ") or line.startswith("\t"):
            current_value += "\n" + line.strip()
        else:
            if current_key:
                _set_deb_field(current_key, current_value, meta)
            if ":" in line:
                current_key, current_value = line.split(":", 1)
                current_key = current_key.strip().lower()
                current_value = current_value.strip()
            else:
                current_key = ""
                current_value = ""

    if current_key:
        _set_deb_field(current_key, current_value, meta)


def _set_deb_field(key: str, value: str, meta: PackageMetadata) -> None:
    """Map a Debian control field to PackageMetadata."""
    if key == "package":
        meta.name = value
    elif key == "version":
        meta.version = value
    elif key == "architecture":
        meta.arch = value
    elif key == "description":
        meta.description = value.split("\n")[0]  # first line only
    elif key == "maintainer":
        meta.maintainer = value
    elif key == "homepage":
        meta.url = value
    elif key == "depends":
        meta.depends = [d.strip().split()[0] for d in value.split(",") if d.strip()]
    elif key == "conflicts":
        meta.conflicts = [c.strip().split()[0] for c in value.split(",") if c.strip()]
    elif key == "installed-size":
        try:
            meta.installed_size_kb = int(value)
        except ValueError:
            pass


def _extract_deb_file_list(
    file_path: Path, data_tar: str, meta: PackageMetadata, tools: ToolPaths
) -> None:
    """List files in data.tar.* without extracting."""
    extract_result = subprocess.run(
        [tools.ar, "p", str(file_path), data_tar],
        capture_output=True,
        timeout=30,
    )
    if extract_result.returncode != 0:
        return

    tar_result = subprocess.run(
        [tools.bsdtar, "-tf", "-"] if tools.bsdtar
        else ["tar", f"-t{_tar_flags_for(data_tar)}f", "-"],
        input=extract_result.stdout,
        capture_output=True,
        timeout=30,
    )
    if tar_result.returncode == 0:
        meta.file_list = [
            line.strip()
            for line in tar_result.stdout.decode("utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().endswith("/")
        ]


def _tar_flags_for(name: str) -> str:
    """Return tar decompression flag for an archive filename."""
    if name.endswith(".gz"):
        return "z"
    elif name.endswith(".xz"):
        return "J"
    elif name.endswith(".bz2"):
        return "j"
    elif name.endswith(".zst"):
        return ""  # bsdtar handles zstd natively
    return ""


# ── .rpm analysis ────────────────────────────────────────────────

def _analyze_rpm(file_path: Path, tools: ToolPaths) -> PackageMetadata:
    """Extract metadata from an RPM package."""
    meta = PackageMetadata(file_path=file_path, package_type="rpm")

    if not tools.rpm2cpio:
        raise RuntimeError("rpm2cpio bulunamadı — rpmextract paketi gerekli")

    # Read RPM header for basic metadata
    _parse_rpm_header(file_path, meta)

    # Map architecture
    meta.arch_mapped = RPM_ARCH_MAP.get(meta.arch, meta.arch)

    # Extract file list via rpm2cpio | bsdtar -tf -
    file_list_result = subprocess.run(
        [tools.rpm2cpio, str(file_path)],
        capture_output=True,
        timeout=30,
    )
    if file_list_result.returncode == 0:
        tar_result = subprocess.run(
            [tools.bsdtar, "-tf", "-"] if tools.bsdtar
            else ["cpio", "-t", "--quiet"],
            input=file_list_result.stdout,
            capture_output=True,
            timeout=30,
        )
        if tar_result.returncode == 0:
            meta.file_list = [
                line.strip()
                for line in tar_result.stdout.decode("utf-8", errors="replace").splitlines()
                if line.strip() and not line.strip().endswith("/")
            ]

    # Check existing installation
    _check_installed(meta, tools)

    log.info("RPM analizi tamamlandı: %s %s (%s)", meta.name, meta.version, meta.arch_mapped)
    return meta


def _parse_rpm_header(file_path: Path, meta: PackageMetadata) -> None:
    """Parse RPM metadata using system 'rpm' command if available, or fallback."""
    import shutil

    with open(file_path, "rb") as f:
        header = f.read(96)

    if len(header) < 4 or header[:4] != b"\xed\xab\xee\xdb":
        raise ValueError("Geçersiz RPM dosyası: magic bytes eşleşmiyor")

    rpm_cmd = shutil.which("rpm")
    if rpm_cmd:
        res = safe_run(
            [rpm_cmd, "-qp", "--queryformat", "%{NAME}\n%{VERSION}\n%{RELEASE}\n%{ARCH}\n%{SUMMARY}\n%{URL}", str(file_path)],
            timeout=10,
        )
        if res.returncode == 0:
            lines = [line.strip() for line in res.stdout.splitlines()]
            if len(lines) >= 4 and lines[0]:
                meta.name = lines[0]
                meta.version = lines[1]
                if len(lines) >= 3 and lines[2] and lines[2] != "(none)":
                    meta.version += f"-{lines[2]}"
                meta.arch = lines[3] if len(lines) >= 4 and lines[3] != "(none)" else "x86_64"
                if len(lines) >= 5 and lines[4] and lines[4] != "(none)":
                    meta.description = lines[4]
                if len(lines) >= 6 and lines[5] and lines[5] != "(none)":
                    meta.url = lines[5]
                return

    # Fallback to byte reading and filename parsing
    arch_num = int.from_bytes(header[8:10], "big") if len(header) >= 10 else 1
    rpm_arch_nums = {1: "x86_64", 2: "i386", 3: "alpha", 12: "aarch64", 0: "noarch"}
    meta.arch = rpm_arch_nums.get(arch_num, "x86_64")
    _parse_rpm_filename(file_path, meta)



def _parse_rpm_filename(file_path: Path, meta: PackageMetadata) -> None:
    """Fallback: parse package name/version from filename.

    Typical: name-version-release.arch.rpm
    """
    stem = file_path.stem  # removes .rpm
    # Remove .arch suffix
    for arch in ("x86_64", "noarch", "i686", "i386", "aarch64"):
        if stem.endswith(f".{arch}"):
            meta.arch = arch
            stem = stem[: -(len(arch) + 1)]
            break

    # Split name-version-release
    match = re.match(r"^(.+?)-(\d.+?)(?:-(\d.+))?$", stem)
    if match:
        meta.name = match.group(1)
        meta.version = match.group(2)
        if match.group(3):
            meta.version += f"-{match.group(3)}"
    elif not meta.name:
        meta.name = stem


# ── Common helpers ───────────────────────────────────────────────

def _check_installed(meta: PackageMetadata, tools: ToolPaths) -> None:
    """Check if a package with this name is already installed."""
    result = safe_run([tools.pacman, "-Qi", meta.name], timeout=10)
    if result.returncode == 0:
        meta.already_installed = True
        for line in result.stdout.splitlines():
            if line.startswith("Sürüm") or line.startswith("Version"):
                meta.installed_version = line.split(":", 1)[1].strip()
                break
        log.info("Mevcut kurulum: %s %s", meta.name, meta.installed_version)
