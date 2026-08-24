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
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from config import APP_NAME, APP_VERSION, ToolPaths, extract_package_name
from core.security import safe_run

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
    # Build toolchain receipt (F5.15): tool versions + debtap-db date.
    build_receipt: dict = field(default_factory=dict)

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


# tar -tv listing shapes. bsdtar: perms nlinks owner group size Mon DD
# HH:MM name — GNU tar: perms owner/group size YYYY-MM-DD HH:MM name.
# Locale month names ("Ağu") are matched as opaque word tokens.
_TV_BSDTAR_RE = re.compile(
    r"^([\-ldbcps][rwxstST-]{9})\s+\d+\s+\S+\s+\S+\s+(\d+)\s+"
    r"\S+\s+\d{1,2}\s+\d{2}:\d{2}\s+(.+)$"
)
_TV_GNU_RE = re.compile(
    r"^([\-ldbcps][rwxstST-]{9})\s+\S+\s+(\d+)\s+"
    r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+(.+)$"
)


def _parse_tv_line(line: str):
    """Return (perms, size, path) from a `tar -tv` line, or None."""
    m = _TV_BSDTAR_RE.match(line) or _TV_GNU_RE.match(line)
    if m is None:
        return None
    return m.group(1), int(m.group(2)), m.group(3).strip()


def _read_pkginfo(pkg_path: Path) -> dict[str, str]:
    """Extract metadata from .PKGINFO inside a .pkg.tar.zst."""
    info: dict[str, str] = {}
    try:
        res = safe_run(
            ["tar", "xf", str(pkg_path), "-O", ".PKGINFO"],
            timeout=10,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if " = " in line:
                    key, val = line.split(" = ", 1)
                    info[key.strip()] = val.strip()
    except Exception as exc:  # noqa: BLE001
        log.debug("PKGINFO okunamadı: %s", exc)
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
    offline: bool = False,
) -> SBOMDocument:
    """Generate a full SBOM for a converted .pkg.tar.zst file.

    Walks every member of the tarball, classifies it, and optionally
    computes SHA-256 for regular files.

    Args:
        pkg_path: Path to the .pkg.tar.zst package.
        tools: Detected system tools.
        include_hashes: When False, sha256 is left empty (faster).
        offline: When True, skip network-dependent operations (dep resolution).

    Returns:
        SBOMDocument with complete file listing.
    """
    sbom = SBOMDocument()
    sbom.created = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sbom.document_name = f"sbom-{pkg_path.name}"

    # Package metadata from .PKGINFO
    pkginfo = _read_pkginfo(pkg_path)
    # Fallback: authoritative name extraction (handles dotted versions and
    # deb/rpm/arch naming; stem.split mis-parses dotted versions).
    sbom.package_name = pkginfo.get("pkgname", "") or extract_package_name(pkg_path.name)
    sbom.package_version = pkginfo.get("pkgver", "")
    sbom.package_arch = pkginfo.get("arch", "")
    sbom.package_description = pkginfo.get("desc", "")

    # F5.15: embed the toolchain receipt (best-effort, never blocks the SBOM).
    try:
        from core.build_receipt import collect_build_receipt

        sbom.build_receipt = collect_build_receipt(tools)
    except Exception:  # noqa: BLE001 - receipt is optional
        sbom.build_receipt = {}

    # List tarball members with sizes
    bsdtar = tools.bsdtar or "bsdtar"
    try:
        res = safe_run(
            [bsdtar, "-tvf", str(pkg_path)],
            timeout=30,
        )
        if res.returncode != 0:
            log.warning("SBOM: tar listing başarısız: %s", res.stderr[:200])
            return sbom

        total_size = 0
        for line in res.stdout.splitlines():
            parsed = _parse_tv_line(line)
            if parsed is None:
                continue

            perms, size, entry_path = parsed

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
                    inner = safe_run(
                        [bsdtar, "-xf", str(pkg_path), "-O", entry_path],
                        timeout=10,
                    )
                    if inner.returncode == 0 and inner.stdout:
                        sha = hashlib.sha256(inner.stdout.encode("utf-8", errors="replace")).hexdigest()
                except Exception as exc:  # noqa: BLE001
                    log.debug("SHA hesaplama başarısız: %s", exc)

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

    except Exception as exc:  # noqa: BLE001
        log.warning("SBOM oluşturma başarısız: %s", exc)

    # Shared-library dependencies (skip in offline mode)
    if not offline:
        try:
            from core.dep_resolver import resolve_runtime_dependencies
            deps = resolve_runtime_dependencies(Path("/"), tools)
            sbom.dependencies = deps
        except Exception as exc:  # noqa: BLE001
            log.debug("Bağımlılık çözümleme başarısız: %s", exc)
    else:
        log.debug("Çevrimdışı mod — bağımlılık çözümleme atlandı")

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


# ── SBOM Diff ──────────────────────────────────────────────────

@dataclass
class SBOMDiff:
    """Diff between two SBOM documents."""

    old_name: str = ""
    new_name: str = ""
    old_version: str = ""
    new_version: str = ""
    added_files: list[str] = field(default_factory=list)
    removed_files: list[str] = field(default_factory=list)
    changed_files: list[dict[str, str]] = field(default_factory=list)  # [{path, old_sha256, new_sha256}]
    changed_deps: list[str] = field(default_factory=list)
    added_deps: list[str] = field(default_factory=list)
    removed_deps: list[str] = field(default_factory=list)
    version_changes: list[dict[str, str]] = field(default_factory=list)
    old_total_files: int = 0
    new_total_files: int = 0
    old_total_size: int = 0
    new_total_size: int = 0

    def summary(self) -> str:
        lines = [
            f"  📦 {self.old_name} {self.old_version} → {self.new_version}",
            (f"  📄 Dosyalar: {self.old_total_files} → {self.new_total_files} ("
             f"+{len(self.added_files)} eklendi, -{len(self.removed_files)} silindi)"),
        ]
        if self.added_deps:
            lines.append(f"  ➕ Yeni bağımlılıklar: {', '.join(self.added_deps[:10])}")
        if self.removed_deps:
            lines.append(f"  ➖ Kaldırılan bağımlılıklar: {', '.join(self.removed_deps[:10])}")
        if self.changed_files:
            lines.append(f"  🔄 Değişen dosyalar: {len(self.changed_files)}")
            for cf in self.changed_files[:5]:
                lines.append(f"     {cf['path']}: {cf['old_sha256']} → {cf['new_sha256']}")
        if self.version_changes:
            lines.append(f"  🔄 Versiyon değişiklikleri: {len(self.version_changes)}")
            for vc in self.version_changes[:5]:
                lines.append(f"     {vc.get('dep', '?')}: {vc.get('old', '?')} → {vc.get('new', '?')}")
        if not any([self.added_files, self.removed_files, self.changed_files, self.added_deps, self.removed_deps, self.version_changes]):
            lines.append("  ✅ Fark yok — paketler aynı")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return asdict(self)


def diff_sboms(old: SBOMDocument, new: SBOMDocument) -> SBOMDiff:
    """Compare two SBOM documents and return a structured diff."""
    diff = SBOMDiff()
    diff.old_name = old.package_name
    diff.new_name = new.package_name
    diff.old_version = old.package_version
    diff.new_version = new.package_version
    diff.old_total_files = old.total_files
    diff.new_total_files = new.total_files
    diff.old_total_size = old.total_size_bytes
    diff.new_total_size = new.total_size_bytes

    # File-level diff
    old_paths = {f.path for f in old.files}
    new_paths = {f.path for f in new.files}
    diff.added_files = sorted(new_paths - old_paths)
    diff.removed_files = sorted(old_paths - new_paths)

    # Content-level diff: compare SHA-256 hashes of common files
    old_file_map = {f.path: f.sha256 for f in old.files if f.sha256}
    new_file_map = {f.path: f.sha256 for f in new.files if f.sha256}
    common_files = old_paths & new_paths
    for path in sorted(common_files):
        old_hash = old_file_map.get(path, "")
        new_hash = new_file_map.get(path, "")
        if old_hash and new_hash and old_hash != new_hash:
            diff.changed_files.append({
                "path": path,
                "old_sha256": old_hash[:16] + "...",
                "new_sha256": new_hash[:16] + "...",
            })

    # Dependency diff
    old_deps = set(old.dependencies)
    new_deps = set(new.dependencies)
    diff.added_deps = sorted(new_deps - old_deps)
    diff.removed_deps = sorted(old_deps - new_deps)

    # Version changes for common deps (not yet tracked — reserved field)
    diff.version_changes = []

    log.info(
        "SBOM diff: +%d -%d files, +%d -%d deps",
        len(diff.added_files), len(diff.removed_files),
        len(diff.added_deps), len(diff.removed_deps),
    )
    return diff


def save_sbom_diff(diff: SBOMDiff, output_path: Path) -> Path:
    """Write the SBOM diff to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(diff.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("SBOM diff kaydedildi: %s", output_path)
    return output_path
