"""PkgForge — Software Bill of Materials (SBOM) Generator.

Generates a JSON SBOM document for converted packages, listing every
bundled file, its detected type, and any shared-library dependencies.
The format is a lightweight JSON document inspired by SPDX and CycloneDX
but kept minimal enough to embed alongside any converted package.

Usage:
    from core.sbom import generate_sbom, save_sbom
    sbom = generate_sbom(Path("app.pkg.tar.zst"), tools)
    save_sbom(sbom, Path("app.pkg.tar.zst.spdx.json"))
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from config import APP_NAME, APP_VERSION, ToolPaths

log = logging.getLogger(__name__)


@dataclass
class SBOMEntry:
    """One file or dependency listed in the SBOM."""

    path: str
    file_type: str = ""        # e.g. "elf", "text", "symlink", "directory"
    sha256: str = ""           # empty for symlinks / dirs
    size_bytes: int = 0
    mime_type: str = ""


@dataclass
class SBOMDocument:
    """Complete SBOM for a converted package."""

    spdx_version: str = "SPDX-2.3"
    document_name: str = ""
    document_namespace: str = ""
    created: str = ""
    tool_name: str = APP_NAME
    tool_version: str = APP_VERSION
    package_name: str = ""
    package_version: str = ""
    package_arch: str = ""
    package_description: str = ""
    # File entries
    files: list[SBOMEntry] = field(default_factory=list)
    # Shared-library dependencies (sonames)
    dependencies: list[str] = field(default_factory=list)
    # Summary counts
    total_files: int = 0
    total_size_bytes: int = 0
    elf_count: int = 0
    text_count: int = 0
    symlink_count: int = 0
    dir_count: int = 0

    def summary(self) -> str:
        lines = [
            f"  📦 Paket:    {self.package_name} {self.package_version} ({self.package_arch})",
            f"  📄 Toplam:   {self.total_files} dosya, {self.total_size_bytes / 1024:.0f} KB",
            f"  🔧 ELF:      {self.elf_count}",
            f"  📝 Metin:    {self.text_count}",
            f"  🔗 Symlink:  {self.symlink_count}",
            f"  📁 Dizin:    {self.dir_count}",
        ]
        if self.dependencies:
            lines.append(f"  🔗 Bağımlılıklar ({len(self.dependencies)}): {', '.join(self.dependencies[:10])}")
            if len(self.dependencies) > 10:
                lines.append(f"     ... ve {len(self.dependencies) - 10} tane daha")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        d = asdict(self)
        d["files"] = [asdict(f) for f in self.files]
        return d


def _read_pkginfo(pkg_path: Path) -> dict[str, str]:
    """Extract metadata from .PKGINFO inside a .pkg.tar.zst."""
    info: dict[str, str] = {}
    try:
        res = subprocess.run(
            ["tar", "xf", str(pkg_path), "-O", ".PKGINFO"],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if " = " in line:
                    key, val = line.split(" = ", 1)
                    info[key.strip()] = val.strip()
    except Exception:
        pass
    return info


def _detect_file_type(path: Path) -> str:
    """Heuristic file-type label."""
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
    except OSError:
        return ""
    if magic == b"\x7fELF":
        return "elf"
    if magic[:2] in (b"#!", b"<\x00"):
        return "text"
    if magic[:3] == b"\xef\xbb\xbf" or magic[:3] == b"\xff\xfe\x00":
        return "text"
    return "binary"


def generate_sbom(
    pkg_path: Path,
    tools: ToolPaths,
    *,
    include_hashes: bool = True,
) -> SBOMDocument:
    """Generate a full SBOM for a converted .pkg.tar.zst file.

    Walks every member of the tarball, classifies it, and optionally
    computes SHA-256 for regular files.

    Args:
        pkg_path: Path to the .pkg.tar.zst package.
        tools: Detected system tools.
        include_hashes: When False, sha256 is left empty (faster).

    Returns:
        SBOMDocument with complete file listing.
    """
    sbom = SBOMDocument()
    sbom.created = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sbom.document_name = f"sbom-{pkg_path.name}"

    # Package metadata from .PKGINFO
    pkginfo = _read_pkginfo(pkg_path)
    sbom.package_name = pkginfo.get("pkgname", pkg_path.stem.split(".")[0])
    sbom.package_version = pkginfo.get("pkgver", "")
    sbom.package_arch = pkginfo.get("arch", "")
    sbom.package_description = pkginfo.get("desc", "")

    # List tarball members with sizes
    bsdtar = tools.bsdtar or "bsdtar"
    try:
        res = subprocess.run(
            [bsdtar, "-tvf", str(pkg_path)],
            capture_output=True, text=True, timeout=30,
        )
        if res.returncode != 0:
            log.warning("SBOM: tar listing başarısız: %s", res.stderr[:200])
            return sbom

        total_size = 0
        for line in res.stdout.splitlines():
            # Example line: "-rw-r--r--  1000/1000   12345 2026-08-20 12:00  usr/bin/app"
            parts = line.split(None, 4)
            if len(parts) < 5:
                continue

            perms = parts[0]
            entry_path = parts[-1].strip()

            # Parse size (field index 3 for standard bsdtar -tvf output)
            try:
                size = int(parts[3]) if parts[3].isdigit() else 0
            except (ValueError, IndexError):
                size = 0

            is_symlink = perms.startswith("l")
            is_dir = perms.startswith("d")

            mime = ""
            file_type = "symlink" if is_symlink else ("directory" if is_dir else "")

            if not is_symlink and not is_dir:
                # Determine MIME by suffix or magic
                if entry_path.endswith((".py", ".sh", ".conf", ".txt", ".md", ".json", ".xml", ".yaml", ".yml")):
                    file_type = "text"
                else:
                    file_type = "binary"

            total_size += size

            # Extract to /dev/null to compute hash without temp files
            sha = ""
            if include_hashes and not is_symlink and not is_dir and size > 0 and size < 10_000_000:
                try:
                    inner = subprocess.run(
                        [bsdtar, "-xf", str(pkg_path), "-O", entry_path],
                        capture_output=True, timeout=10,
                    )
                    if inner.returncode == 0 and inner.stdout:
                        sha = hashlib.sha256(inner.stdout).hexdigest()
                except Exception:
                    pass

            sbom.files.append(SBOMEntry(
                path=entry_path,
                file_type=file_type,
                sha256=sha,
                size_bytes=size,
                mime_type=mime,
            ))

        sbom.total_files = len(sbom.files)
        sbom.total_size_bytes = total_size
        sbom.elf_count = sum(1 for f in sbom.files if f.file_type == "elf")
        sbom.text_count = sum(1 for f in sbom.files if f.file_type == "text")
        sbom.symlink_count = sum(1 for f in sbom.files if f.file_type == "symlink")
        sbom.dir_count = sum(1 for f in sbom.files if f.file_type == "directory")

    except Exception as exc:
        log.warning("SBOM oluşturma başarısız: %s", exc)

    # Shared-library dependencies
    try:
        from core.dep_resolver import resolve_runtime_dependencies
        deps = resolve_runtime_dependencies(Path("/"), tools)
        sbom.dependencies = deps
    except Exception:
        pass

    return sbom


def save_sbom(sbom: SBOMDocument, output_path: Path) -> Path:
    """Write the SBOM document to a JSON file.

    Returns the path written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = sbom.to_dict()
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("SBOM kaydedildi: %s", output_path)
    return output_path
