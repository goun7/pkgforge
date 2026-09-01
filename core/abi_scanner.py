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

from core.constants import TIMEOUT_FAST, TIMEOUT_MEDIUM, TIMEOUT_SLOW
from core.security import safe_run
from i18n import tr

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
class NamcapResult:
    """Namcap static analysis result for a single finding."""

    severity: str  # "error" | "warning" | "info"
    tag: str       # namcap tag name (e.g., "htar-warning")
    message: str   # Human-readable description
    file: str = "" # Associated file path (if any)


@dataclass
class ABIScanReport:
    """Complete ABI compatibility scan report."""

    binary_count: int = 0
    mismatches: list[SymbolMismatch] = field(default_factory=list)
    missing_libs: list[tuple[str, str]] = field(default_factory=list)  # (binary, lib)
    checked_symbols: int = 0
    namcap_results: list[NamcapResult] = field(default_factory=list)
    namcap_available: bool = False

    @property
    def passed(self) -> bool:
        has_namcap_errors = any(r.severity == "error" for r in self.namcap_results)
        return len(self.mismatches) == 0 and len(self.missing_libs) == 0 and not has_namcap_errors

    @property
    def error_count(self) -> int:
        namcap_errs = sum(1 for r in self.namcap_results if r.severity == "error")
        return len(self.mismatches) + len(self.missing_libs) + namcap_errs

    def summary(self) -> str:
        lines = [
            tr("abi.taranan_elf_dosyasi_self", self_binary_count=self.binary_count),
            f"  🔎 Kontrol edilen sembol: {self.checked_symbols}",
            tr("abi.sembol_uyumsuzlugu_mismatches", mismatches=len(self.mismatches)),
            tr("abi.eksik_kutuphane_missing_libs", missing_libs=len(self.missing_libs)),
        ]
        if self.namcap_available:
            n_errors = sum(1 for r in self.namcap_results if r.severity == "error")
            n_warns = sum(1 for r in self.namcap_results if r.severity == "warning")
            n_info = sum(1 for r in self.namcap_results if r.severity == "info")
            lines.append(tr("abi.namcap_errors_hata_warns", n_errors=n_errors, n_warns=n_warns, n_info=n_info))
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
        if self.namcap_results:
            lines.append("")
            lines.append("  Namcap Bulguları:")
            for r in self.namcap_results[:20]:
                icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(r.severity, "•")
                loc = f" ({r.file})" if r.file else ""
                lines.append(f"    {icon} [{r.tag}] {r.message}{loc}")
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
    res = safe_run(
        [readelf, "-V", str(elf_path)], timeout=TIMEOUT_FAST,
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

    res = safe_run(
        [readelf, "-V", str(lib_path)], timeout=TIMEOUT_FAST,
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

    res = safe_run(
        [readelf, "-s", "--version-info", str(elf_path)], timeout=TIMEOUT_FAST,
    )
    if res.returncode != 0:
        return None

    for line in res.stdout.splitlines():
        if version_tag in line:
            parts = line.split()
            if len(parts) >= 8:
                return parts[7]  # Symbol name column
    return None


def _run_namcap(pkg_path: Path) -> list[NamcapResult]:
    """Run namcap static analysis on a package file.

    Args:
        pkg_path: Path to .pkg.tar.zst or .deb file.

    Returns:
        List of NamcapResult objects.
    """
    namcap = shutil.which("namcap")
    if not namcap:
        return []

    results: list[NamcapResult] = []
    try:
        res = safe_run(
            [namcap, str(pkg_path)], timeout=TIMEOUT_SLOW,
        )
        # namcap output format:
        # PKGBUILD (line N): warning: description should not be empty
        # PKGBUILD (line N): error: depends contains not a dependency
        # file.txt (line 1): info: refer to https://wiki.archlinux.org/...
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("namcap:"):
                continue

            severity = "info"
            if ": error:" in line or ": error " in line:
                severity = "error"
            elif ": warning:" in line or ": warning " in line:
                severity = "warning"

            # Parse tag from line
            tag_match = re.search(r'\b(error|warning|info):\s+(\S+)', line)
            tag = tag_match.group(2) if tag_match else "unknown"

            # Extract file reference
            file_match = re.match(r'^(\S+)', line)
            file_ref = file_match.group(1) if file_match and ":" in line else ""

            # Clean message
            msg = line
            if ":" in msg:
                parts = msg.split(":", 2)
                if len(parts) >= 3:
                    msg = parts[2].strip()

            results.append(NamcapResult(
                severity=severity,
                tag=tag,
                message=msg[:200],
                file=file_ref,
            ))

    except (subprocess.TimeoutExpired, OSError) as exc:
        log.debug(tr("abi.namcap_calisamadi_s"), exc)

    return results


def _extract_pkg_for_abi(pkg_path: Path, tmp: Path) -> bool:
    """Paketi tmp icine cikarir (DEB: ar+data.tar, PKG: dogrudan tar).

    Bilinmeyen uzantida False doner (tarama atlanir, hata degil).
    """
    if ".deb" in pkg_path.name:
        # DEB: extract data.tar
        try:
            import shlex
            cmd = f"ar x {shlex.quote(str(pkg_path))} data.tar.*"
            safe_run(
                ["/bin/bash", "-c", cmd],
                cwd=str(tmp), timeout=TIMEOUT_MEDIUM,
            )
            # Find and extract data.tar
            for dtar in tmp.glob("data.tar.*"):
                safe_run(
                    ["tar", "xf", str(dtar), "-C", str(tmp)], timeout=TIMEOUT_MEDIUM,
                )
                dtar.unlink()
                break
        except (subprocess.TimeoutExpired, OSError):
            return False
    elif ".pkg.tar" in pkg_path.name:
        safe_run(
            ["tar", "xf", str(pkg_path), "-C", str(tmp)], timeout=TIMEOUT_MEDIUM,
        )
    else:
        return False
    return True


def _collect_elf_binaries(tmp: Path) -> list[Path]:
    """Tek gecisle ELF ikililerini toplar (bilinen metin/asset uzantilari atlanir).

    Tek gecis bilinclidir: ayni dizin agacini iki kez gezmemek icin
    kesif ve isim listesi ayni dongude birlesir.
    """
    skip_exts = {
        ".py", ".txt", ".conf", ".json", ".xml", ".png", ".jpg", ".svg",
        ".md", ".rst", ".html", ".css", ".js", ".ts", ".yaml", ".yml",
        ".toml", ".ini", ".cfg", ".sh", ".bash", ".desktop", ".service",
    }
    elf_files: list[Path] = []
    for candidate in sorted(tmp.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() in skip_exts:
            continue
        if candidate.name.startswith(".") or candidate.name.startswith("_"):
            continue
        if _is_elf_binary(candidate):
            elf_files.append(candidate)
    return elf_files


def _ldd_missing_libs(elf_files: list[Path], tmp: Path) -> list[tuple[str, str]]:
    """Her ikilide ldd calistirir; (rel path, eksik kutuphane) ciftlerini dondurur.

    Bilincli risk pencesi: yalniz sistem ldd'i (shutil.which) cagrilir —
    paket iceriginden hicbir yurutme yapilmaz.
    """
    ldd = shutil.which("ldd")
    if not (ldd and elf_files):
        return []
    ldd_results: dict[str, list[str]] = {}
    for elf in elf_files:
        try:
            ldd_res = safe_run(
                [ldd, str(elf)], timeout=TIMEOUT_FAST,
            )
            missing = [
                line.strip().split()[0]
                for line in ldd_res.stdout.splitlines()
                if "not found" in line
            ]
            if missing:
                ldd_results[str(elf.relative_to(tmp))] = missing
        except (subprocess.TimeoutExpired, OSError) as exc:
            log.debug("ldd taramasi atlandi (%s): %s", elf, exc)
    pairs: list[tuple[str, str]] = []
    for rel_path, libs in ldd_results.items():
        for lib in libs:
            pairs.append((rel_path, lib))
    return pairs


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

        if not _extract_pkg_for_abi(pkg_path, tmp):
            return report

        # Step 1: Collect all ELF binaries (single pass)
        elf_files = _collect_elf_binaries(tmp)
        report.binary_count = len(elf_files)

        # Step 2: Batch ldd — single subprocess per binary but all collected first
        report.missing_libs = _ldd_missing_libs(elf_files, tmp)

        # Step 3: Check symbol versions for each ELF
        readelf = _get_readelf()
        if readelf and elf_files:
            for elf in elf_files:
                rel_path = str(elf.relative_to(tmp))
                mismatches = scan_elf_symbols(elf)
                for m in mismatches:
                    m.binary = rel_path
                report.mismatches.extend(mismatches)
                report.checked_symbols += len(mismatches)

        # Run namcap static analysis on the package
        namcap = shutil.which("namcap")
        if namcap:
            report.namcap_available = True
            report.namcap_results = _run_namcap(pkg_path)

    return report
