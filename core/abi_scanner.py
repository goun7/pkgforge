"""PkgForge — ABI Compatibility Scanner.

Detects GLIBC/GLIBCXX symbol version mismatches between converted packages
and the host system. This catches "installed but won't run" issues that
simple ldd checks miss.

Usage:
    from core.abi_scanner import scan_elf_symbols, check_abi_compatibility

    mismatches = scan_elf_symbols(Path("/usr/bin/myapp"))
    # Returns list of SymbolMismatch objects

    report = check_abi_compatibility(Path("myapp.pkg.tar.zst"))
    # Returns ABIScanReport with all findings
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class SymbolMismatch:
    """A single symbol version mismatch."""

    binary: str          # ELF binary path (relative)
    symbol: str          # Symbol name
    required_version: str  # Version needed (e.g., GLIBC_2.33)
    available_version: str  # Version on system (e.g., GLIBC_2.31)
    library: str         # Shared library name (e.g., libc.so.6)
    severity: str = "error"  # "error" or "warning"


@dataclass
class ABIScanReport:
    """Complete ABI compatibility scan report."""

    binary_count: int = 0
    mismatches: list[SymbolMismatch] = field(default_factory=list)
    missing_libs: list[tuple[str, str]] = field(default_factory=list)  # (binary, lib)
    checked_symbols: int = 0

    @property
    def passed(self) -> bool:
        return len(self.mismatches) == 0 and len(self.missing_libs) == 0

    @property
    def error_count(self) -> int:
        return len(self.mismatches) + len(self.missing_libs)

    def summary(self) -> str:
        lines = [
            f"  🔍 Taranan ELF dosyası: {self.binary_count}",
            f"  🔎 Kontrol edilen sembol: {self.checked_symbols}",
            f"  ❌ Sembol uyumsuzluğu: {len(self.mismatches)}",
            f"  📦 Eksik kütüphane: {len(self.missing_libs)}",
        ]
        if self.mismatches:
            lines.append("")
            lines.append("  Uyumsuz Semboller:")
            for m in self.mismatches[:20]:
                lines.append(
                    f"    {m.severity.upper():>7}  {m.binary}: "
                    f"{m.symbol} (gerekli: {m.required_version}, "
                    f"mevcut: {m.available_version})"
                )
        if self.missing_libs:
            lines.append("")
            lines.append("  Eksik Kütüphaneler:")
            for binary, lib in self.missing_libs[:20]:
                lines.append(f"    ❌  {binary}: {lib}")
        return "\n".join(lines)


def _is_elf_binary(file_path: Path) -> bool:
    """Check if a file is an ELF binary."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(4)
        return header == b"\x7fELF"
    except (OSError, PermissionError):
        return False


def _get_readelf() -> str | None:
    """Find readelf binary."""
    return shutil.which("readelf") or shutil.which("/usr/bin/readelf")


def _get_objcopy() -> str | None:
    """Find objcopy binary."""
    return shutil.which("objcopy") or shutil.which("/usr/bin/objcopy")


def scan_elf_symbols(elf_path: Path) -> list[SymbolMismatch]:
    """Scan a single ELF binary for GLIBC/GLIBCXX symbol version requirements.

    Uses readelf to extract dynamic symbol versions and compares them
    with what's available on the host system.

    Args:
        elf_path: Path to the ELF binary.

    Returns:
        List of SymbolMismatch objects for symbols that need newer versions.
    """
    mismatches: list[SymbolMismatch] = []
    readelf = _get_readelf()
    if not readelf:
        return mismatches

    # Get required symbol versions from the binary
    res = subprocess.run(
        [readelf, "-V", str(elf_path)],
        capture_output=True, text=True, timeout=10,
    )
    if res.returncode != 0:
        return mismatches

    # Parse readelf -V output
    # Format: Version needs section '.gnu.version_r' contains 2 entries:
    #   Addr: 0x...  Offset: 0x...  Link: 5 (.dynstr)
    #   000000: Version: 1  File: libc.so.6  Cnt: 3
    #   0x0010:   Name: GLIBC_2.33  Flags: none  Version: 4
    #   0x0020:   Name: GLIBC_2.34  Flags: none  Version: 5

    current_file = ""
    for line in res.stdout.splitlines():
        line = line.strip()

        # Detect library reference
        file_match = re.search(r'File:\s+(\S+)', line)
        if file_match:
            current_file = file_match.group(1)
            continue

        # Detect version requirement
        name_match = re.search(r'Name:\s+(GLIBC_\d+\.\d+(\.\d+)?|GLIBCXX_\d+\.\d+(\.\d+)?)', line)
        if name_match and current_file:
            required_version = name_match.group(1)
            # Check if this version is available on the system
            available = _check_version_available(required_version)
            if not available:
                # Find the symbol name from VERNEED section
                sym_name = _extract_symbol_for_version(elf_path, required_version)
                mismatches.append(SymbolMismatch(
                    binary=str(elf_path.name),
                    symbol=sym_name or f"({required_version})",
                    required_version=required_version,
                    available_version=available or "yok",
                    library=current_file,
                    severity="error",
                ))

    return mismatches


def _check_version_available(version_tag: str) -> str | None:
    """Check if a GLIBC/GLIBCXX version tag is available on the system.

    Returns the available version string if >= required, None otherwise.
    """
    # Determine library type
    if version_tag.startswith("GLIBC_"):
        lib_names = ["libc.so.6", "libc.so"]
    elif version_tag.startswith("GLIBCXX_"):
        lib_names = ["libstdc++.so.6", "libstdc++.so"]
    else:
        return None

    # Parse required version
    req_parts = version_tag.split("_", 1)[1].split(".")
    req_major = int(req_parts[0]) if len(req_parts) > 0 else 0
    req_minor = int(req_parts[1]) if len(req_parts) > 1 else 0
    req_patch = int(req_parts[2]) if len(req_parts) > 2 else 0

    # Find the library on the system
    for lib_name in lib_names:
        # Search standard paths
        search_paths = [
            Path("/usr/lib"),
            Path("/usr/lib64"),
            Path("/lib"),
            Path("/lib64"),
            Path("/usr/lib/x86_64-linux-gnu"),
        ]

        for base in search_paths:
            if not base.is_dir():
                continue
            for lib_file in base.glob(f"{lib_name}*"):
                if not lib_file.is_file() or lib_file.is_symlink():
                    continue
                # Use readelf to check available versions
                available = _get_available_versions(lib_file)
                for av in available:
                    if av.startswith(version_tag.split("_")[0] + "_"):
                        av_parts = av.split("_", 1)[1].split(".")
                        av_major = int(av_parts[0]) if len(av_parts) > 0 else 0
                        av_minor = int(av_parts[1]) if len(av_parts) > 1 else 0
                        av_patch = int(av_parts[2]) if len(av_parts) > 2 else 0
                        if (av_major, av_minor, av_patch) >= (req_major, req_minor, req_patch):
                            return av
    return None


def _get_available_versions(lib_path: Path) -> list[str]:
    """Get list of available symbol versions from a shared library."""
    readelf = _get_readelf()
    if not readelf:
        return []

    res = subprocess.run(
        [readelf, "-V", str(lib_path)],
        capture_output=True, text=True, timeout=10,
    )
    if res.returncode != 0:
        return []

    versions = []
    for line in res.stdout.splitlines():
        match = re.search(r'Name:\s+((?:GLIBC|GLIBCXX)_\d+\.\d+(\.\d+)?)', line.strip())
        if match:
            versions.append(match.group(1))
    return versions


def _extract_symbol_for_version(elf_path: Path, version_tag: str) -> str | None:
    """Try to find the symbol name associated with a version tag."""
    readelf = _get_readelf()
    if not readelf:
        return None

    res = subprocess.run(
        [readelf, "-s", "--version-info", str(elf_path)],
        capture_output=True, text=True, timeout=10,
    )
    if res.returncode != 0:
        return None

    for line in res.stdout.splitlines():
        if version_tag in line:
            parts = line.split()
            if len(parts) >= 8:
                return parts[7]  # Symbol name column
    return None


def check_abi_compatibility(pkg_path: Path) -> ABIScanReport:
    """Check ABI compatibility of all ELF binaries in a package.

    Extracts the package, scans all ELF binaries for GLIBC/GLIBCXX
    symbol version requirements, and checks them against the host system.

    Args:
        pkg_path: Path to .pkg.tar.zst or .deb file.

    Returns:
        ABIScanReport with all mismatches found.
    """
    report = ABIScanReport()

    with tempfile.TemporaryDirectory(prefix="pkgforge_abi_") as tmpdir:
        tmp = Path(tmpdir)

        # Extract package
        if ".deb" in pkg_path.name:
            # DEB: extract data.tar
            try:
                import shlex
                cmd = f"ar x {shlex.quote(str(pkg_path))} data.tar.*"
                subprocess.run(
                    ["/bin/bash", "-c", cmd],
                    cwd=str(tmp), capture_output=True, timeout=30,
                )
                # Find and extract data.tar
                for dtar in tmp.glob("data.tar.*"):
                    subprocess.run(
                        ["tar", "xf", str(dtar), "-C", str(tmp)],
                        capture_output=True, timeout=30,
                    )
                    dtar.unlink()
                    break
            except (subprocess.TimeoutExpired, OSError):
                return report
        elif ".pkg.tar" in pkg_path.name:
            subprocess.run(
                ["tar", "xf", str(pkg_path), "-C", str(tmp)],
                capture_output=True, timeout=30,
            )
        else:
            return report

        # Scan all files for ELF binaries
        for candidate in sorted(tmp.rglob("*")):
            if not candidate.is_file():
                continue
            skip_exts = {
                ".py", ".txt", ".conf", ".json", ".xml", ".png", ".jpg", ".svg",
                ".md", ".rst", ".html", ".css", ".js", ".ts", ".yaml", ".yml",
                ".toml", ".ini", ".cfg", ".sh", ".bash", ".desktop", ".service",
            }
            if candidate.suffix.lower() in skip_exts:
                continue
            if candidate.name.startswith(".") or candidate.name.startswith("_"):
                continue

            if not _is_elf_binary(candidate):
                continue

            report.binary_count += 1
            rel_path = str(candidate.relative_to(tmp))

            # Check symbol versions
            mismatches = scan_elf_symbols(candidate)
            for m in mismatches:
                m.binary = rel_path
            report.mismatches.extend(mismatches)
            report.checked_symbols += len(mismatches)

            # Also check ldd for missing libs
            ldd = shutil.which("ldd")
            if ldd:
                try:
                    ldd_res = subprocess.run(
                        [ldd, str(candidate)],
                        capture_output=True, text=True, timeout=5,
                    )
                    for line in ldd_res.stdout.splitlines():
                        if "not found" in line:
                            lib_name = line.strip().split()[0]
                            report.missing_libs.append((rel_path, lib_name))
                except (subprocess.TimeoutExpired, OSError):
                    pass

    return report
