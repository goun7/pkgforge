"""PkgForge — Compatibility checker.

Runs namcap analysis, dependency resolution, shared library checks,
deep ldd analysis, glibc version check, and file conflict detection
on converted packages.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from config import ToolPaths
from core.dep_resolver import (
    parse_needed_sonames,
    parse_objdump_rpath_dirs,
    parse_objdump_sonames,
    parse_rpath_dirs,
)
from core.maps import debian_dep_to_arch
from core.security import is_valid_package_name, safe_run
from i18n import tr

log = logging.getLogger(__name__)

# `file --mime-type` output for ELF artifacts worth dependency analysis.
# x-pie-executable MUST be listed: modern toolchains (and all Arch packages)
# build PIE by default, and omitting it silently excluded every real binary
# from the shared-library check, making it report "all libraries present".
_ELF_ANALYSABLE_MIMES = frozenset({
    "application/x-executable",
    "application/x-pie-executable",
    "application/x-sharedlib",
})


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report for the JSON-RPC sidecar / desktop UI."""
        return {
            "overall": self.overall.value,
            "grade": self.grade,
            "checks": [
                {
                    "name": c.name,
                    "severity": c.severity.value,
                    "message": c.message,
                    "details": list(c.details),
                }
                for c in self.checks
            ],
        }


def run_compatibility_checks(
    pkg_path: Path,
    file_list: list[str],
    depends: list[str],
    tools: ToolPaths,
    maintainer_scripts: list[str] | None = None,
) -> CompatibilityReport:
    """Run all compatibility checks on a converted package.

    Args:
        pkg_path:  Path to the .pkg.tar.zst file.
        file_list: List of file paths the package will install.
        depends:   List of dependency package names.
        tools:     Discovered tool paths.
        maintainer_scripts: Hooks shipped by the source package, if any.
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

    # 5. Maintainer scripts dropped by the conversion
    report.checks.append(_check_maintainer_scripts(maintainer_scripts or []))

    log.info(
        tr("compat.uyumluluk_raporu_d_kontrol_d"),
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
            name=tr("compat.namcap"),
            severity=CheckSeverity.WARNING,
            message=tr("compat.namcap_missing"),
        )

    result = safe_run([tools.namcap, "-m", str(pkg_path)], timeout=60)
    output = result.stdout.strip() + "\n" + result.stderr.strip()
    output = output.strip()

    if not output:
        return CheckResult(
            name=tr("compat.namcap"),
            severity=CheckSeverity.PASS,
            message=tr("compat.namcap_clean"),
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
            name=tr("compat.namcap"),
            severity=CheckSeverity.ERROR,
            message=tr("compat.errors_hata_warnings_uyari", errors=len(errors), warnings=len(warnings)),
            details=errors + warnings,
        )
    elif warnings:
        return CheckResult(
            name=tr("compat.namcap"),
            severity=CheckSeverity.WARNING,
            message=tr("compat.warnings_uyari_tespit_edildi", warnings=len(warnings)),
            details=warnings,
        )
    else:  # pragma: no cover — dış strip() en az bir dolu satır garantiler
        return CheckResult(
            name=tr("compat.namcap"),
            severity=CheckSeverity.PASS,
            message=tr("compat.no_issues"),
        )


# ── Dependency resolution ────────────────────────────────────────

def _check_dependencies(depends: list[str], tools: ToolPaths) -> list[CheckResult]:
    """Check if each dependency can be resolved by pacman."""
    if not depends:
        return [
            CheckResult(
                name=tr("compat.deps"),
                severity=CheckSeverity.PASS,
                message=tr("compat.no_deps"),
            )
        ]
    if not tools.pacman:
        # Non-Arch host (CI/dev): no pacman db to consult; report skipped.
        return [
            CheckResult(
                name=tr("compat.deps"),
                severity=CheckSeverity.WARNING,
                message=tr("compat.deps_pacman_missing"),
            )
        ]

    resolved: list[str] = []
    missing: list[str] = []

    for dep in depends:
        # Strip version constraints for lookup
        dep_name = re.split(r"[><=()]", dep)[0].strip()
        if not dep_name:
            continue

        # Debian-sourced names (libc6, libstdc++6, ...) are normalized to
        # Arch equivalents first; unknown foreign names are kept as-is and
        # reported honestly below instead of guessed.
        mapped = debian_dep_to_arch(dep_name)
        lookup_name = mapped or dep_name
        display_name = (
            f"{dep_name} → {mapped}" if mapped and mapped != dep_name else dep_name
        )

        # Dep names come from untrusted package metadata; validate before
        # passing to pacman so a crafted name cannot inject CLI options.
        if not is_valid_package_name(lookup_name):
            missing.append(tr("compat.dep_name_gecersiz_ad", dep_name=lookup_name))
            continue

        # Check if installed
        qi = safe_run([tools.pacman, "-Qi", lookup_name], timeout=5)
        if qi.returncode == 0:
            resolved.append(display_name)
            continue

        # Check if available in repos
        si = safe_run([tools.pacman, "-Si", lookup_name], timeout=5)
        if si.returncode == 0:
            resolved.append(display_name)
            continue

        # Dynamic lookup: pacman -Fq
        pf = safe_run([tools.pacman, "-Fq", lookup_name], timeout=5)
        if pf.returncode == 0 and pf.stdout.strip():
            matched_pkg = pf.stdout.strip().splitlines()[0].split("/")[-1]
            resolved.append(f"{display_name} → {matched_pkg}")
            continue

        missing.append(display_name)


    results: list[CheckResult] = []

    if missing:
        results.append(
            CheckResult(
                name=tr("compat.deps"),
                severity=CheckSeverity.WARNING,
                message=tr("compat.missing_depends_bagimlilik_cozumlen", missing=len(missing), depends=len(depends)),
                details=[f"❌ {d}" for d in missing],
            )
        )
    else:
        results.append(
            CheckResult(
                name=tr("compat.deps"),
                severity=CheckSeverity.PASS,
                message=tr("compat.tum_bagimliliklar_resolved_cozumlen", resolved=len(resolved)),
                details=[f"✓ {d}" for d in resolved],
            )
        )

    return results


# ── File conflicts ───────────────────────────────────────────────

def _check_file_conflicts(file_list: list[str], tools: ToolPaths) -> CheckResult:
    """Check if any files would conflict with existing packages."""
    if not file_list:
        return CheckResult(
            name=tr("compat.conflicts"),
            severity=CheckSeverity.PASS,
            message=tr("compat.empty_file_list"),
        )
    if not tools.pacman:
        return CheckResult(
            name=tr("compat.conflicts"),
            severity=CheckSeverity.WARNING,
            message=tr("compat.conflicts_pacman_missing"),
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

        # A crafted file path could start with '-' and be parsed as an option;
        # the '--' separator keeps pacman from treating it as a flag.
        result = safe_run([tools.pacman, "-Qo", "--", fpath], timeout=5)
        if result.returncode == 0:
            # File is owned by another package
            owner = result.stdout.strip()
            conflicts.append(f"{fpath} → {owner}")

    if conflicts:
        return CheckResult(
            name=tr("compat.conflicts"),
            severity=CheckSeverity.WARNING,
            message=tr("compat.conflicts_dosya_mevcut_paketlerle", conflicts=len(conflicts)),
            details=conflicts[:20],  # limit display
        )

    return CheckResult(
        name=tr("compat.conflicts"),
        severity=CheckSeverity.PASS,
        message=tr("compat.check_files_dosya_kontrol", check_files=len(check_files)),
    )


# ── Shared library check ────────────────────────────────────────

def _list_package_elf_files(
    pkg_path: Path, tools: ToolPaths,
) -> tuple[list[str] | None, str]:
    """Paket icindeki ELF aday dosyalari.

    (dosyalar, durum) doner: durum "arac" (araclar eksik), "liste"
    (icerik listelenemedi) ya da "" (basarili; dosyalar bos olabilir).
    """
    reader = tools.readelf or tools.objdump
    if not tools.bsdtar or not reader:
        return None, "arac"
    result = safe_run([tools.bsdtar, "-tf", str(pkg_path)], timeout=30)
    if result.returncode != 0:
        return None, "liste"
    elf_patterns = re.compile(r"\.(so(\.\d+)*|bin)$|/bin/|/sbin/|/lib/|/lib64/")
    files = [
        f for f in result.stdout.splitlines()
        if elf_patterns.search(f) and not f.endswith("/")
    ]
    return files, ""


def _loader_search_dirs() -> set[str]:
    """Directories the dynamic loader searches for sonames on this system.

    glibc always searches the compiled-in defaults, then whatever ld.so.conf
    lists. A library shipped into a directory outside this set is present on
    disk but invisible to the linker, which is the classic converted-.deb
    breakage (Debian's /usr/lib/x86_64-linux-gnu is searched on Debian, not on
    Arch).
    """
    dirs = {"/usr/lib", "/lib"}
    try:
        lines = Path("/etc/ld.so.conf").read_text(
            encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return dirs
    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("include "):
            dirs |= _read_ld_conf_paths_from_glob(entry.split(None, 1)[1])
        else:
            dirs.add(entry)
    return dirs


def _read_ld_conf_paths_from_glob(pattern: str) -> set[str]:
    """Expand an ld.so.conf ``include`` glob and collect the directories it names."""
    from glob import glob as _glob

    dirs: set[str] = set()
    for path in _glob(pattern):
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            entry = line.strip()
            if entry and not entry.startswith("#") and not entry.startswith("include "):
                dirs.add(entry)
    return dirs


def _shipped_lib_dirs(tmpdir: Path) -> dict[str, list[Path]]:
    """Map soname -> extracted locations for libraries the package ships itself.

    Keys are basenames (as the loader sees them); values are paths inside
    *tmpdir*, so the caller can judge *where* the library would land, not just
    that it exists.
    """
    out: dict[str, list[Path]] = {}
    for p in tmpdir.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        if name.endswith(".so") or ".so." in name:
            out.setdefault(name, []).append(p)
    return out


def _lib_reachable(
    lib_path: Path,
    elf_path: Path,
    tmpdir: Path,
    rpath: list[str],
    loader_dirs: set[str],
) -> bool:
    """Can the loader actually find *lib_path* for *elf_path* at runtime?

    True if the library's would-be install directory is a loader search dir, or
    the ELF names that directory in RPATH/RUNPATH (absolute entry, or a
    ``$ORIGIN``-relative one that resolves onto it).
    """
    install_dir = "/" + str(lib_path.relative_to(tmpdir).parent)
    if install_dir in loader_dirs:
        return True
    if not rpath:
        return False
    origin = str(elf_path.parent)
    for entry in rpath:
        if entry.startswith("$ORIGIN"):
            resolved = os.path.normpath(origin + entry[len("$ORIGIN"):])
            if resolved == str(lib_path.parent):
                return True
        elif entry in install_dir or entry == install_dir:
            return True
    return False


def _analyze_elf_dependencies(
    elf_to_check: list[Path], tmpdir: Path, tools: ToolPaths,
) -> tuple[list[str], list[str], int, list[str]]:
    """Statik DT_NEEDED + glibc analizi; ldd CALISTIRILMAZ (PT_INTERP riski).

    (missing_libs, glibc_issues, checked_count, unreachable_libs) doner.
    """
    missing_libs: list[str] = []
    glibc_issues: list[str] = []
    unreachable: list[str] = []
    checked_count = 0

    system_libs = _system_lib_sonames()
    shipped = _shipped_lib_dirs(tmpdir)
    loader_dirs = _loader_search_dirs()

    for elf_path in elf_to_check[:15]:
        checked_count += 1
        try:
            if tools.readelf:
                res = safe_run([tools.readelf, "-d", str(elf_path)], timeout=10)
                sonames = parse_needed_sonames(res.stdout)
                rpath = parse_rpath_dirs(res.stdout)
            else:
                res = safe_run([tools.objdump, "-p", str(elf_path)], timeout=10)
                sonames = parse_objdump_sonames(res.stdout)
                rpath = parse_objdump_rpath_dirs(res.stdout)
        except Exception as exc:  # noqa: BLE001
            log.debug("NEEDED okunamadi (%s): %s", elf_path.name, exc)
            continue

        for soname in sonames:
            if soname in system_libs:
                continue
            candidates = shipped.get(soname, [])
            if not candidates:
                if soname not in missing_libs:
                    missing_libs.append(soname)
                continue
            # Shipped is not the same as loadable: a library in a directory the
            # linker never searches (and not named by RPATH) still fails to open.
            if not any(_lib_reachable(c, elf_path, tmpdir, rpath, loader_dirs)
                       for c in candidates):
                note = f"{soname} ({elf_path.name})"
                if note not in unreachable:
                    unreachable.append(note)

        req_glibc = _elf_max_glibc(elf_path, tools)
        if req_glibc:
            sys_glibc = _get_system_glibc(tools)
            if sys_glibc and _version_gt(req_glibc, sys_glibc):
                issue = f"{elf_path.name}: GLIBC_{req_glibc} gerekli (sistemde: {sys_glibc})"
                if issue not in glibc_issues:
                    glibc_issues.append(issue)

    return missing_libs, glibc_issues, checked_count, unreachable


def _shared_lib_result(
    missing_libs: list[str], glibc_issues: list[str], checked_count: int,
    unreachable: list[str] | None = None,
) -> CheckResult:
    """Analiz sonucunu CheckResult'a cevirir (oncelik: glibc > eksik > temiz)."""
    unreachable = unreachable or []
    if glibc_issues:
        return CheckResult(
            name=tr("compat.so"),
            severity=CheckSeverity.ERROR,
            message=tr("compat.glibc_incompatible", n_issues=len(glibc_issues)),
            details=glibc_issues + [f"Eksik: {lib}" for lib in missing_libs],
        )
    if missing_libs or unreachable:
        parts: list[str] = []
        if missing_libs:
            parts.append(tr("compat.libs_eksik", count=len(missing_libs)))
        if unreachable:
            parts.append(tr("compat.libs_erisilemez", count=len(unreachable)))
        return CheckResult(
            name=tr("compat.so"),
            severity=CheckSeverity.WARNING,
            message=" — ".join(parts),
            details=[f"Eksik: {lib}" for lib in missing_libs]
            + [tr("compat.libs_erisilemez_detail", note=n) for n in unreachable],
        )
    return CheckResult(
        name=tr("compat.so"),
        severity=CheckSeverity.PASS,
        message=tr("compat.all_libs_present", checked_count=checked_count),
    )


def _check_shared_libraries(pkg_path: Path, tools: ToolPaths) -> CheckResult:
    """Deep shared library check using static analysis only.

    Security: we deliberately do **not** run ldd on extracted binaries —
    ldd *executes* the target PT_INTERP loader, so a malicious package could
    run arbitrary code during a compatibility scan. Instead we read DT_NEEDED
    entries statically with readelf -d / objdump -p (same approach as
    the dependency resolver) and compare against the ldconfig -p cache.
    """
    import shutil
    import tempfile

    elf_files, durum = _list_package_elf_files(pkg_path, tools)
    if durum == "arac":
        return CheckResult(
            name=tr("compat.so"),
            severity=CheckSeverity.WARNING,
            message=tr("compat.elf_tools_missing"),
        )
    if durum == "liste":
        return CheckResult(
            name=tr("compat.so"),
            severity=CheckSeverity.WARNING,
            message=tr("compat.pkg_list_failed"),
        )
    assert elf_files is not None
    if not elf_files:
        return CheckResult(
            name=tr("compat.so"),
            severity=CheckSeverity.PASS,
            message=tr("compat.no_elf_in_package"),
        )

    # Extract ELF files to temp dir for static analysis
    tmpdir = Path(tempfile.mkdtemp(prefix="pkgforge_ldd_"))
    missing_libs: list[str] = []
    glibc_issues: list[str] = []
    unreachable: list[str] = []
    checked_count = 0

    try:
        # Extract package
        safe_run(
            [tools.bsdtar, "-xf", str(pkg_path), "-C", str(tmpdir)],
            timeout=60,
        )

        # Find actual ELF files using the file command (does not execute them).
        # Archive member names are untrusted: reject absolute paths and any
        # containing .. so a crafted member cannot point readelf at a host
        # file outside the extraction dir.
        elf_to_check: list[Path] = []
        for elf_rel in elf_files[:30]:  # Limit to 30 files
            if elf_rel.startswith("/") or ".." in elf_rel:
                log.warning("Supheli arsiv uyesi atlandi: %s", elf_rel)
                continue
            elf_abs = (tmpdir / elf_rel).resolve()
            if not str(elf_abs).startswith(str(tmpdir.resolve()) + os.sep):
                log.warning("Dizin disi ELF yolu atlandi: %s", elf_rel)
                continue
            if elf_abs.is_file():
                file_result = safe_run(
                    [tools.file_cmd, "--mime-type", "-b", str(elf_abs)],
                    timeout=5,
                )
                mime = file_result.stdout.strip()
                # Substring match: `file --mime-type` may append "; charset=...".
                if any(kind in mime for kind in _ELF_ANALYSABLE_MIMES):
                    elf_to_check.append(elf_abs)

        missing_libs, glibc_issues, checked_count, unreachable = (
            _analyze_elf_dependencies(elf_to_check, tmpdir, tools))
    except Exception as exc:  # noqa: BLE001
        log.warning("Shared library analizi hatasi: %s", exc)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return _shared_lib_result(missing_libs, glibc_issues, checked_count, unreachable)


def _system_lib_sonames() -> set[str]:
    """Return sonames known to the system dynamic linker cache.

    Uses ``ldconfig -p`` (read-only listing, no execution of package files).
    """
    import shutil
    ldconfig_bin = shutil.which("ldconfig")
    if not ldconfig_bin:
        return set()
    try:
        result = safe_run([ldconfig_bin, "-p"], timeout=10)
    except Exception as exc:  # noqa: BLE001
        log.debug(tr("compat.ldconfig_sorgulanamadi_s"), exc)
        return set()

    sonames: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if "=>" in line:
            name = line.split("=>")[0].strip().split()[0]
            if name:
                sonames.add(name)
    return sonames


def _elf_max_glibc(elf_path: Path, tools: ToolPaths) -> str:
    """Return the highest GLIBC_x.y(.z) version an ELF requires (static read).

    Parses ``readelf --version-info`` output; never executes the binary.
    """
    if not tools.readelf:
        return ""
    try:
        res = safe_run([tools.readelf, "--version-info", str(elf_path)], timeout=10)
    except Exception as exc:  # noqa: BLE001
        log.debug(tr("compat.readelf_version_bilgisi_alinamadi_s"), exc)
        return ""
    versions = re.findall(r"GLIBC_(\d+\.\d+(\.\d+)?)", res.stdout)
    if not versions:
        return ""
    best = "0.0"
    for ver, _ in versions:
        if _version_gt(ver, best):
            best = ver
    return best if best != "0.0" else ""


def _get_system_glibc(tools: ToolPaths) -> str:
    """Get the system's glibc version via ``ldd --version`` (safe, no target execution)."""
    if not tools.ldd:
        return ""
    try:
        result = safe_run([tools.ldd, "--version"], timeout=5)
        for line in result.stdout.splitlines():
            match = re.search(r"(\d+\.\d+(\.\d+)?)", line)
            if match:
                return match.group(1)
    except Exception as exc:  # noqa: BLE001
        log.debug(tr("compat.abi_version_regex_basarisiz_s"), exc)
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

# ── Maintainer scripts ───────────────────────────────────────────

#: Debian/OpenSuse script name -> the Arch .INSTALL hook it would map to.
_SCRIPT_HOOK_MAP = {
    "preinst": "pre_install / pre_upgrade",
    "postinst": "post_install / post_upgrade",
    "prerm": "pre_remove",
    "postrm": "post_remove",
}


def describe_script_hook(name: str) -> str:
    """Return the Arch .INSTALL hook a Debian/RPM maintainer script maps to."""
    return _SCRIPT_HOOK_MAP.get(name, "?")


def _check_maintainer_scripts(scripts: list[str]) -> CheckResult:
    """Report source-package maintainer scripts the conversion cannot carry.

    Arch runs no postinst/postrm: the equivalent is an .INSTALL hook, which a
    converted package cannot have because its logic is Debian/RPM-specific.
    Silently dropping it is how a converted app ends up "installed but broken",
    so this is surfaced as a warning rather than left invisible.
    """
    name = tr("compat.scripts.name")
    if not scripts:
        return CheckResult(
            name=name,
            severity=CheckSeverity.PASS,
            message=tr("compat.scripts.temiz"),
        )
    return CheckResult(
        name=name,
        severity=CheckSeverity.WARNING,
        message=tr("compat.scripts.dusuruldu", count=len(scripts),
                    scripts=", ".join(scripts)),
        details=[
            tr("compat.scripts.hook", script=s, hook=describe_script_hook(s))
            for s in scripts
        ],
    )
