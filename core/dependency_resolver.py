"""PkgForge — Runtime dependency resolver.

Best-effort mapping of a converted package's *actual* shared-library needs to
the Arch Linux packages that provide them, so generated PKGBUILDs declare real,
installable dependencies instead of foreign (deb/rpm) package names that
`pacman -U` cannot satisfy.

Design goals (safety first):
- Never execute the target binaries — sonames are read statically via
  ``readelf -d`` (falls back to ``objdump -p``).
- Never raise into the conversion flow — on any problem the public helpers
  return what they have so far (possibly empty). An empty ``depends()`` still
  installs cleanly, which is strictly safer than declaring a bogus dependency.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from config import ToolPaths
from core.security import safe_run

log = logging.getLogger(__name__)

# readelf -d prints:  0x0000...(NEEDED)  Shared library: [libc.so.6]
_NEEDED_RE = re.compile(r"NEEDED\)\s+Shared library:\s+\[([^\]]+)\]")
# objdump -p prints:  NEEDED               libc.so.6
_OBJDUMP_NEEDED_RE = re.compile(r"^\s*NEEDED\s+(\S+)\s*$", re.MULTILINE)

_ELF_MAGIC = b"\x7fELF"


def parse_needed_sonames(readelf_output: str) -> list[str]:
    """Extract DT_NEEDED sonames from ``readelf -d`` output."""
    return _NEEDED_RE.findall(readelf_output)


def parse_objdump_sonames(objdump_output: str) -> list[str]:
    """Extract NEEDED sonames from ``objdump -p`` output."""
    return _OBJDUMP_NEEDED_RE.findall(objdump_output)


def is_elf_file(path: Path) -> bool:
    """Return True if *path* starts with the ELF magic bytes (no execution)."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == _ELF_MAGIC
    except OSError:
        return False


def collect_sonames(root_dir: Path, tools: ToolPaths, *, max_files: int = 200) -> set[str]:
    """Walk *root_dir*, statically read each ELF's DT_NEEDED sonames."""
    reader = tools.readelf or tools.objdump
    if not reader:
        return set()

    sonames: set[str] = set()
    checked = 0
    for path in root_dir.rglob("*"):
        if checked >= max_files:
            break
        if not path.is_file() or path.is_symlink():
            continue
        if not is_elf_file(path):
            continue
        checked += 1
        try:
            if tools.readelf:
                res = safe_run([tools.readelf, "-d", str(path)], timeout=10)
                sonames.update(parse_needed_sonames(res.stdout))
            else:
                res = safe_run([tools.objdump, "-p", str(path)], timeout=10)
                sonames.update(parse_objdump_sonames(res.stdout))
        except Exception as exc:  # never break conversion over one binary
            log.debug("soname okunamadı (%s): %s", path.name, exc)
    return sonames


def sonames_to_packages(sonames: set[str], tools: ToolPaths) -> list[str]:
    """Map each soname to the Arch package that owns it via ``pacman -Fq``.

    Only packages confirmed by pacman are returned; unknown sonames are dropped.
    Requires a synced files database (``pacman -Fy``); if unsynced this returns
    an empty list (safe).
    """
    if not tools.pacman:
        return []

    packages: set[str] = set()
    for soname in sonames:
        # Skip the dynamic loader itself; it is provided by glibc implicitly.
        if soname.startswith("ld-") or soname.startswith("ld-linux"):
            packages.add("glibc")
            continue
        try:
            res = safe_run([tools.pacman, "-Fq", soname], timeout=8)
        except Exception:
            continue
        if res.returncode != 0 or not res.stdout.strip():
            continue
        # Output lines look like "core/glibc" or "extra/gtk3"; take the pkg name.
        for line in res.stdout.strip().splitlines():
            pkg = line.strip().split("/")[-1].split()[0]
            if pkg:
                packages.add(pkg)
                break
    return sorted(packages)


def resolve_runtime_dependencies(root_dir: Path, tools: ToolPaths) -> list[str]:
    """Return the confirmed Arch package dependencies for a build tree.

    Best-effort and non-raising: returns ``[]`` when the environment cannot
    resolve dependencies (missing readelf/objdump, unsynced pacman file DB, or
    a tree with no ELF binaries).
    """
    try:
        sonames = collect_sonames(root_dir, tools)
        if not sonames:
            return []
        packages = sonames_to_packages(sonames, tools)
        log.info(
            "Bağımlılık çözümü: %d soname → %d Arch paketi", len(sonames), len(packages)
        )
        return packages
    except Exception as exc:
        log.warning("Bağımlılık çözümü başarısız: %s", exc)
        return []
