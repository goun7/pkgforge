"""PkgForge — Smart Dependency Resolver.

Resolves missing dependencies by checking:
1. Official Arch repos (pacman)
2. AUR (via aurutils, paru, or yay)
3. If not found: suggests Distrobox fallback

Usage:
    from core.dep_resolver import resolve_dependencies
    report = resolve_dependencies(["libfoo", "libbar>=2.0", "custom-tool"])
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from urllib.request import Request, urlopen
from urllib.error import URLError

log = logging.getLogger(__name__)


@dataclass
class DepStatus:
    """Status of a single dependency."""

    name: str
    required_version: str = ""
    resolved: bool = False
    source: str = ""  # "pacman" | "aur" | "not_found"
    installed_version: str = ""
    aur_package: str = ""  # AUR package name if different from dep name


@dataclass
class ResolveReport:
    """Complete dependency resolution report."""

    deps: list[DepStatus] = field(default_factory=list)
    all_resolved: bool = False
    total: int = 0
    resolved_count: int = 0
    missing_count: int = 0

    def summary(self) -> str:
        lines = [
            f"  Toplam bağımlılık: {self.total}",
            f"  Çözümlenen:        {self.resolved_count}",
            f"  Eksik:             {self.missing_count}",
        ]
        if self.missing_count > 0:
            lines.append("")
            lines.append("  Eksik bağımlılıklar:")
            for d in self.deps:
                if not d.resolved:
                    lines.append(f"    ❌ {d.name}{d.required_version} — {d.source}")
        return "\n".join(lines)


def _parse_dep_string(dep_str: str) -> tuple[str, str]:
    """Parse 'foo>=2.0' into ('foo', '>=2.0')."""
    # Remove leading/trailing whitespace
    dep_str = dep_str.strip()

    # Try common operators
    for op in [">=", "<=", ">", "<", "="]:
        if op in dep_str:
            parts = dep_str.split(op, 1)
            if len(parts) == 2 and parts[0].strip():
                return parts[0].strip(), op + parts[1].strip()

    return dep_str, ""


def _check_pacman(name: str) -> tuple[bool, str]:
    """Check if a package is available in official repos."""
    pacman = shutil.which("pacman")
    if not pacman:
        return False, ""

    res = subprocess.run(
        [pacman, "-Si", name],
        capture_output=True, text=True, timeout=10,
    )
    if res.returncode == 0:
        # Extract version
        for line in res.stdout.splitlines():
            if line.startswith("Version"):
                ver = line.split(":", 1)[1].strip()
                return True, ver
        return True, "unknown"
    return False, ""


def _check_pacman_installed(name: str) -> tuple[bool, str]:
    """Check if a package is installed."""
    pacman = shutil.which("pacman")
    if not pacman:
        return False, ""

    res = subprocess.run(
        [pacman, "-Qi", name],
        capture_output=True, text=True, timeout=10,
    )
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            if line.startswith("Version"):
                ver = line.split(":", 1)[1].strip()
                return True, ver
        return True, "unknown"
    return False, ""


def _aur_helper() -> str | None:
    """Find available AUR helper."""
    for helper in ["paru", "yay", "aurutils"]:
        if shutil.which(helper):
            return helper
    return None


def _check_aur(name: str) -> tuple[bool, str]:
    """Check if a package is in the AUR."""
    # Method 1: Try AUR RPC with retry
    try:
        from core.retry import retry_aur_rpc

        rpc_url = f"https://aur.archlinux.org/rpc/v5/info/{name}"
        data = retry_aur_rpc(rpc_url, max_retries=2, timeout=10)
        if data.get("resultcount", 0) > 0:
            pkg = data["results"][0]
            aur_name = pkg.get("Name", "")
            aur_ver = pkg.get("Version", "")
            return True, aur_ver if aur_name else ""
    except Exception:
        pass

    # Method 2: Try AUR helper
    helper = _aur_helper()
    if helper:
        res = subprocess.run(
            [helper, "-Si", name],
            capture_output=True, text=True, timeout=15,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "Version" in line:
                    ver = line.split(":", 1)[1].strip() if ":" in line else ""
                    return True, ver
            return True, "unknown"

    return False, ""


def resolve_dependencies(
    depends: list[str],
    include_installed: bool = True,
) -> ResolveReport:
    """Resolve a list of dependencies.

    For each dependency:
    1. Check if installed (if include_installed)
    2. Check official repos
    3. Check AUR
    4. Mark as not_found if all fail

    Args:
        depends: List of dependency strings (e.g., ["foo", "bar>=2.0"])
        include_installed: If True, consider installed packages as resolved.

    Returns:
        ResolveReport with resolution status for each dependency.
    """
    report = ResolveReport()
    report.total = len(depends)

    for dep_str in depends:
        dep_name, required_ver = _parse_dep_string(dep_str)
        status = DepStatus(name=dep_name, required_version=required_ver)

        # Skip virtual packages / capabilities
        if dep_name.startswith("virtual/") or not dep_name:
            continue

        # 1. Check if installed
        if include_installed:
            installed, installed_ver = _check_pacman_installed(dep_name)
            if installed:
                status.resolved = True
                status.source = "pacman (installed)"
                status.installed_version = installed_ver
                report.deps.append(status)
                report.resolved_count += 1
                continue

        # 2. Check official repos
        in_repo, repo_ver = _check_pacman(dep_name)
        if in_repo:
            status.resolved = True
            status.source = "pacman (official)"
            status.installed_version = repo_ver
            report.deps.append(status)
            report.resolved_count += 1
            continue

        # 3. Check AUR
        in_aur, aur_ver = _check_aur(dep_name)
        if in_aur:
            status.resolved = True
            status.source = "aur"
            status.installed_version = aur_ver
            status.aur_package = dep_name
            report.deps.append(status)
            report.resolved_count += 1
            continue

        # 4. Not found
        status.resolved = False
        status.source = "not_found"
        report.deps.append(status)
        report.missing_count += 1

    report.all_resolved = report.missing_count == 0
    return report


def install_aur_packages(packages: list[str], aur_helper: str | None = None) -> tuple[bool, str]:
    """Install AUR packages using an AUR helper.

    Args:
        packages: List of AUR package names.
        aur_helper: Path to AUR helper (auto-detected if None).

    Returns:
        (success, message)
    """
    if not aur_helper:
        aur_helper = _aur_helper()
    if not aur_helper:
        return False, "AUR helper bulunamadı (paru veya yay)"

    cmd = [aur_helper, "-S", "--needed", "--noconfirm"] + packages
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if res.returncode == 0:
        return True, f"{len(packages)} paket kuruldu: {', '.join(packages)}"
    else:
        return False, f"Kurulum başarısız: {res.stderr[:300]}"
