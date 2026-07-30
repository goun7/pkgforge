"""PkgForge — Compatibility checker.

Runs namcap analysis, dependency resolution, shared library checks,
deep ldd analysis, glibc version check, and file conflict detection
on converted packages.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from config import ToolPaths
from core.security import safe_run

log = logging.getLogger(__name__)


class CheckSeverity(Enum):
    PASS = "pass"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class CheckResult:
    """A single compatibility check result."""
    name: str
    severity: CheckSeverity
    message: str
    details: list[str] = field(default_factory=list)


@dataclass
class CompatibilityReport:
    """Full compatibility report for a converted package."""
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def overall(self) -> CheckSeverity:
        if any(c.severity == CheckSeverity.ERROR for c in self.checks):
            return CheckSeverity.ERROR
        if any(c.severity == CheckSeverity.WARNING for c in self.checks):
            return CheckSeverity.WARNING
        return CheckSeverity.PASS

    @property
    def errors(self) -> list[CheckResult]:
        return [c for c in self.checks if c.severity == CheckSeverity.ERROR]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if c.severity == CheckSeverity.WARNING]

    @property
    def passed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.severity == CheckSeverity.PASS]

    @property
    def grade(self) -> str:
        """Return a letter grade (A–F) summarizing installation confidence.

        Derived purely from the collected checks so the CLI and GUI show the
        same score:
            A = clean, B/C = warnings only, D/F = one or more blocking errors.
        """
        n_err = len(self.errors)
        n_warn = len(self.warnings)
        if n_err >= 2:
            return "F"
        if n_err == 1:
            return "D"
        if n_warn >= 3:
            return "C"
        if n_warn >= 1:
            return "B"
        return "A"


def run_compatibility_checks(
    pkg_path: Path,
    file_list: list[str],
    depends: list[str],
    tools: ToolPaths,
) -> CompatibilityReport:
    """Run all compatibility checks on a converted package.

    Args:
        pkg_path:  Path to the .pkg.tar.zst file.
        file_list: List of file paths the package will install.
        depends:   List of dependency package names.
        tools:     Discovered tool paths.
    """
    report = CompatibilityReport()

    # 1. Namcap analysis
    report.checks.append(_run_namcap(pkg_path, tools))

    # 2. Dependency resolution
    dep_results = _check_dependencies(depends, tools)
    report.checks.extend(dep_results)

    # 3. File conflicts
    conflict_result = _check_file_conflicts(file_list, tools)
    report.checks.append(conflict_result)

    # 4. Shared library check
    if tools.ldd:
        so_result = _check_shared_libraries(pkg_path, tools)
        report.checks.append(so_result)

    log.info(
        "Uyumluluk raporu: %d kontrol, %d hata, %d uyarı",
        len(report.checks),
        len(report.errors),
        len(report.warnings),
    )
    return report


# ── Namcap ───────────────────────────────────────────────────────

def _run_namcap(pkg_path: Path, tools: ToolPaths) -> CheckResult:
    """Run namcap static analysis on the package."""
    if not tools.namcap:
        return CheckResult(
            name="Namcap Analizi",
            severity=CheckSeverity.WARNING,
            message="namcap bulunamadı, statik analiz atlandı",
        )

    result = safe_run([tools.namcap, "-m", str(pkg_path)], timeout=60)
    output = result.stdout.strip() + "\n" + result.stderr.strip()
    output = output.strip()

    if not output:
        return CheckResult(
            name="Namcap Analizi",
            severity=CheckSeverity.PASS,
            message="Namcap herhangi bir sorun tespit etmedi",
        )

    errors: list[str] = []
    warnings: list[str] = []

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if " E: " in line or "(E)" in line:
            errors.append(line)
        elif " W: " in line or "(W)" in line:
            warnings.append(line)
        else:
            warnings.append(line)  # treat unknowns as warnings

    if errors:
        return CheckResult(
            name="Namcap Analizi",
            severity=CheckSeverity.ERROR,
            message=f"{len(errors)} hata, {len(warnings)} uyarı tespit edildi",
            details=errors + warnings,
        )
    elif warnings:
        return CheckResult(
            name="Namcap Analizi",
            severity=CheckSeverity.WARNING,
            message=f"{len(warnings)} uyarı tespit edildi (hata yok)",
            details=warnings,
        )
    else:
        return CheckResult(
            name="Namcap Analizi",
            severity=CheckSeverity.PASS,
            message="Sorun tespit edilmedi",
        )


# ── Dependency resolution ────────────────────────────────────────

def _check_dependencies(depends: list[str], tools: ToolPaths) -> list[CheckResult]:
    """Check if each dependency can be resolved by pacman."""
    if not depends:
        return [
            CheckResult(
                name="Bağımlılık Kontrolü",
                severity=CheckSeverity.PASS,
                message="Paket bağımlılığı yok",
            )
        ]

    resolved: list[str] = []
    missing: list[str] = []
    version_mismatch: list[str] = []

    for dep in depends:
        # Strip version constraints for lookup
        dep_name = re.split(r"[><=()]", dep)[0].strip()
        if not dep_name:
            continue

        # Check if installed
        qi = safe_run([tools.pacman, "-Qi", dep_name], timeout=5)
        if qi.returncode == 0:
            resolved.append(dep_name)
            continue

        # Check if available in repos
        si = safe_run([tools.pacman, "-Si", dep_name], timeout=5)
        if si.returncode == 0:
            resolved.append(dep_name)
            continue

        # Dynamic lookup: pacman -Fq
        pf = safe_run([tools.pacman, "-Fq", dep_name], timeout=5)
        if pf.returncode == 0 and pf.stdout.strip():
            matched_pkg = pf.stdout.strip().splitlines()[0].split("/")[-1]
            resolved.append(f"{dep_name} → {matched_pkg}")
            continue

        missing.append(dep_name)


    results: list[CheckResult] = []

    if missing:
        results.append(
            CheckResult(
                name="Bağımlılık Kontrolü",
                severity=CheckSeverity.WARNING,
                message=f"{len(missing)}/{len(depends)} bağımlılık çözümlenemedi",
                details=[f"❌ {d}" for d in missing],
            )
        )
    else:
        results.append(
            CheckResult(
                name="Bağımlılık Kontrolü",
                severity=CheckSeverity.PASS,
                message=f"Tüm bağımlılıklar ({len(resolved)}) çözümlendi",
                details=[f"✓ {d}" for d in resolved],
            )
        )

    return results


# ── File conflicts ───────────────────────────────────────────────

def _check_file_conflicts(file_list: list[str], tools: ToolPaths) -> CheckResult:
    """Check if any files would conflict with existing packages."""
    if not file_list:
        return CheckResult(
            name="Dosya Çakışması",
            severity=CheckSeverity.PASS,
            message="Dosya listesi boş, çakışma kontrolü atlandı",
        )

    conflicts: list[str] = []

    # Only check a reasonable subset (max 50 files)
    check_files = [f for f in file_list if not f.endswith("/")][:50]

    for fpath in check_files:
        # Normalize path
        if fpath.startswith("./"):
            fpath = fpath[1:]
        elif not fpath.startswith("/"):
            fpath = "/" + fpath

        result = safe_run([tools.pacman, "-Qo", fpath], timeout=5)
        if result.returncode == 0:
            # File is owned by another package
            owner = result.stdout.strip()
            conflicts.append(f"{fpath} → {owner}")

    if conflicts:
        return CheckResult(
            name="Dosya Çakışması",
            severity=CheckSeverity.WARNING,
            message=f"{len(conflicts)} dosya mevcut paketlerle çakışıyor",
            details=conflicts[:20],  # limit display
        )

    return CheckResult(
        name="Dosya Çakışması",
        severity=CheckSeverity.PASS,
        message=f"{len(check_files)} dosya kontrol edildi, çakışma yok",
    )


# ── Shared library check ────────────────────────────────────────

def _check_shared_libraries(pkg_path: Path, tools: ToolPaths) -> CheckResult:
    """Deep shared library check: extract ELF binaries, run ldd, detect issues."""
    import shutil
    import tempfile

    if not tools.bsdtar or not tools.ldd:
        return CheckResult(
            name="Shared Library Kontrolü",
            severity=CheckSeverity.WARNING,
            message="ldd veya bsdtar bulunamadı, kontrol atlandı",
        )

    # List files in the package
    result = safe_run(
        [tools.bsdtar, "-tf", str(pkg_path)],
        timeout=30,
    )
    if result.returncode != 0:
        return CheckResult(
            name="Shared Library Kontrolü",
            severity=CheckSeverity.WARNING,
            message="Paket içeriği listelenemedi",
        )

    elf_patterns = re.compile(r"\.(so(\.\d+)*|bin)$|/bin/|/sbin/|/lib/|/lib64/")
    elf_files = [
        f for f in result.stdout.splitlines()
        if elf_patterns.search(f) and not f.endswith("/")
    ]

    if not elf_files:
        return CheckResult(
            name="Shared Library Kontrolü",
            severity=CheckSeverity.PASS,
            message="Pakette ELF dosyası tespit edilmedi",
        )

    # Extract ELF files to temp dir for ldd analysis
    tmpdir = Path(tempfile.mkdtemp(prefix="pkgforge_ldd_"))
    missing_libs: list[str] = []
    glibc_issues: list[str] = []
    checked_count = 0

    try:
        # Extract package
        safe_run(
            [tools.bsdtar, "-xf", str(pkg_path), "-C", str(tmpdir)],
            timeout=60,
        )

        # Find actual ELF files using 'file' command
        elf_to_check: list[Path] = []
        for elf_rel in elf_files[:30]:  # Limit to 30 files
            elf_abs = tmpdir / elf_rel.lstrip("./")
            if elf_abs.is_file():
                file_result = safe_run(
                    [tools.file_cmd, "--mime-type", "-b", str(elf_abs)],
                    timeout=5,
                )
                mime = file_result.stdout.strip()
                if "application/x-executable" in mime or "application/x-sharedlib" in mime:
                    elf_to_check.append(elf_abs)

        # Run ldd on each ELF binary
        for elf_path in elf_to_check[:15]:  # Limit analysis scope
            ldd_result = safe_run(
                [tools.ldd, str(elf_path)],
                timeout=10,
            )
            checked_count += 1

            for line in ldd_result.stdout.splitlines():
                line = line.strip()
                if "not found" in line:
                    lib_name = line.split("=>")[0].strip() if "=>" in line else line.split()[0]
                    if lib_name not in missing_libs:
                        missing_libs.append(lib_name)

            # Check for glibc version requirements
            for line in ldd_result.stdout.splitlines():
                glibc_match = re.search(r"GLIBC_(\d+\.\d+(\.\d+)?)", line)
                if glibc_match:
                    required_ver = glibc_match.group(1)
                    # Get system glibc version
                    sys_glibc = _get_system_glibc(tools)
                    if sys_glibc and _version_gt(required_ver, sys_glibc):
                        issue = f"{elf_path.name}: GLIBC_{required_ver} gerekli (sistemde: {sys_glibc})"
                        if issue not in glibc_issues:
                            glibc_issues.append(issue)

    except Exception as exc:
        log.warning("LDD analizi hatası: %s", exc)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Build result
    all_issues = missing_libs + glibc_issues
    if glibc_issues:
        return CheckResult(
            name="Shared Library Kontrolü",
            severity=CheckSeverity.ERROR,
            message=f"glibc uyumsuzluğu tespit edildi ({len(glibc_issues)} sorun)",
            details=glibc_issues + [f"Eksik: {lib}" for lib in missing_libs],
        )
    elif missing_libs:
        return CheckResult(
            name="Shared Library Kontrolü",
            severity=CheckSeverity.WARNING,
            message=f"{len(missing_libs)} eksik kütüphane tespit edildi",
            details=[f"Eksik: {lib}" for lib in missing_libs],
        )
    else:
        return CheckResult(
            name="Shared Library Kontrolü",
            severity=CheckSeverity.PASS,
            message=f"{checked_count} ELF dosyası analiz edildi, tüm kütüphaneler mevcut",
        )


def _get_system_glibc(tools: ToolPaths) -> str:
    """Get the system's glibc version."""
    try:
        result = safe_run([tools.ldd, "--version"], timeout=5)
        for line in result.stdout.splitlines():
            match = re.search(r"(\d+\.\d+(\.\d+)?)", line)
            if match:
                return match.group(1)
    except Exception:
        pass
    return ""


def _version_gt(ver_a: str, ver_b: str) -> bool:
    """Return True if ver_a > ver_b (simple numeric comparison)."""
    a_parts = [int(x) for x in ver_a.split(".")]
    b_parts = [int(x) for x in ver_b.split(".")]
    for a, b in zip(a_parts, b_parts):
        if a > b:
            return True
        if a < b:
            return False
    return len(a_parts) > len(b_parts)
