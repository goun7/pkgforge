"""PkgForge — Dependency Graph Visualization.

Generates text-based dependency graphs for converted packages.
Supports both package-level (pacman deps) and file-level (shared library)
dependency graphs with proper ELF binary detection.

Usage:
    pkgforge graph <package>          # Show dependency graph
    pkgforge graph <package> --files  # Show file dependency graph
    pkgforge graph <package> --format mermaid  # Mermaid output
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from config import extract_package_name
from core.security import safe_run
from i18n import tr

log = logging.getLogger(__name__)


@dataclass
class DepNode:
    """A single node in the dependency graph."""

    name: str
    version: str = ""
    deps: list[str] = field(default_factory=list)
    needed_by: list[str] = field(default_factory=list)
    is_installed: bool = False
    is_foreign: bool = False  # not in official repos


@dataclass
class DepGraph:
    """Full dependency graph for a package."""

    root: str = ""
    nodes: dict[str, DepNode] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def add_edge(self, source: str, target: str) -> None:
        """Add a dependency edge: source depends on target."""
        if source not in self.nodes:
            self.nodes[source] = DepNode(name=source)
        if target not in self.nodes:
            self.nodes[target] = DepNode(name=target)
        if target not in self.nodes[source].deps:
            self.nodes[source].deps.append(target)
        if source not in self.nodes[target].needed_by:
            self.nodes[target].needed_by.append(source)

    def to_mermaid(self) -> str:
        """Render as Mermaid flowchart."""
        lines = ["graph TD"]
        for name, node in self.nodes.items():
            safe_name = name.replace("-", "_").replace(".", "_").replace("/", "_")
            label = name
            if node.version:
                label += f" v{node.version}"
            if node.is_installed:
                lines.append(f'    {safe_name}["{label}"]')
            else:
                lines.append(f'    {safe_name}{{{{"{label}"}}}}')

            for dep in node.deps:
                dep_safe = dep.replace("-", "_").replace(".", "_").replace("/", "_")
                lines.append(f"    {safe_name} --> {dep_safe}")

        return "\n".join(lines)

    def to_ascii(self) -> str:
        """Render as simple ASCII tree."""
        if not self.root:
            root = next(iter(self.nodes)) if self.nodes else ""
        else:
            root = self.root

        lines: list[str] = []
        visited: set[str] = set()

        def _draw(name: str, prefix: str = "", is_last: bool = True) -> None:
            if name in visited:
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{name} (circular ref ↑)")
                return
            visited.add(name)

            node = self.nodes.get(name, DepNode(name=name))
            connector = "└── " if is_last else "├── "
            suffix = ""
            if node.version:
                suffix = f" v{node.version}"
            if not node.is_installed:
                suffix += " ⚠️ MISSING"
            lines.append(f"{prefix}{connector}{name}{suffix}")

            child_prefix = prefix + ("    " if is_last else "│   ")
            deps = node.deps
            for i, dep in enumerate(deps):
                _draw(dep, child_prefix, i == len(deps) - 1)

        _draw(root)
        return "\n".join(lines)

    def stats(self) -> dict:
        """Get summary statistics."""
        total = len(self.nodes)
        installed = sum(1 for n in self.nodes.values() if n.is_installed)
        foreign = sum(1 for n in self.nodes.values() if n.is_foreign)
        max_depth = self._max_depth()
        return {
            "total": total,
            "installed": installed,
            "missing": total - installed,
            "foreign": foreign,
            "max_depth": max_depth,
        }

    def _max_depth(self) -> int:
        """Calculate maximum dependency depth."""
        if not self.root or self.root not in self.nodes:
            return 0

        visited: set[str] = set()

        def _depth(name: str) -> int:
            if name in visited or name not in self.nodes:
                return 0
            visited.add(name)
            node = self.nodes[name]
            if not node.deps:
                return 1
            child_depths = [_depth(d) for d in node.deps]
            return 1 + max(child_depths) if child_depths else 1

        return _depth(self.root)


def _parse_dep_name(dep_entry: str) -> str:
    """Extract package name from a dependency string like 'foo>=2.0'."""
    # Remove version constraints: >= <= = > < etc.
    for op in [">=", "<=", "=", ">", "<"]:
        if op in dep_entry:
            dep_entry = dep_entry.split(op)[0]
    return dep_entry.strip()


def _is_elf_binary(file_path: Path) -> bool:
    """Check if a file is an ELF binary using the file(1) command."""
    file_cmd = shutil.which("file")
    if not file_cmd:
        # Fallback: check ELF magic bytes
        try:
            with open(file_path, "rb") as f:
                header = f.read(4)
            return header == b"\x7fELF"
        except (OSError, PermissionError):
            return False

    try:
        res = safe_run(
            [file_cmd, "--brief", str(file_path)], timeout=5,
        )
        output = res.stdout.lower()
        return "elf" in output or "executable" in output or "shared object" in output
    except (subprocess.TimeoutExpired, OSError):
        return False


def build_dep_graph(pkg_path: Path) -> DepGraph:
    """Build a dependency graph from a converted .pkg.tar.zst file.

    Uses pacman to query the package's dependencies and checks
    which ones are installed on the system. If the package is not
    installed, generates a warning.

    Args:
        pkg_path: Path to .pkg.tar.zst or package name.

    Returns:
        DepGraph with nodes and edges populated.
    """
    graph = DepGraph()
    pacman = shutil.which("pacman")
    if not pacman:
        graph.warnings.append("pacman bulunamadı — grafik oluşturulamıyor")
        return graph

    # Extract package name from filename or use as-is. Delegate to the
    # authoritative extractor (handles .pkg.tar.* naming and bare names).
    graph.root = extract_package_name(pkg_path.name)

    # Query package dependencies
    res = safe_run(
        [pacman, "-Qi", graph.root], timeout=10,
    )
    if res.returncode != 0:
        graph.warnings.append(
            tr("depgraph.graph_root_kurulu_degil", graph_root=graph.root)
        )
        # Try reading from .PKGINFO if the file is a .pkg.tar.zst
        if pkg_path.is_file() and ".pkg.tar" in pkg_path.name:
            graph = _build_from_pkginfo(pkg_path, graph)
        return graph

    # Parse pacman output
    in_deps = False
    for line in res.stdout.splitlines():
        if line.startswith("Name"):
            graph.root = line.split(":", 1)[1].strip()
        elif line.startswith("Version"):
            graph.nodes[graph.root] = DepNode(
                name=graph.root,
                version=line.split(":", 1)[1].strip(),
                is_installed=True,
            )
        elif line.startswith("Depends On"):
            deps_str = line.split(":", 1)[1].strip()
            if deps_str and deps_str != "None":
                in_deps = True
                for dep_entry in deps_str.split():
                    dep_name = _parse_dep_name(dep_entry)
                    if dep_name and dep_name != "None":
                        graph.add_edge(graph.root, dep_name)
            else:
                in_deps = False
        elif in_deps and line.startswith("  "):
            # Continuation line for long dependency lists
            for dep_entry in line.strip().split():
                dep_name = _parse_dep_name(dep_entry)
                if dep_name and dep_name != "None":
                    graph.add_edge(graph.root, dep_name)

    # Check which deps are installed
    for dep_name, dep_node in list(graph.nodes.items()):
        if dep_name == graph.root:
            continue
        dep_res = safe_run(
            [pacman, "-Qi", dep_name], timeout=5,
        )
        if dep_res.returncode == 0:
            dep_node.is_installed = True
            for line in dep_res.stdout.splitlines():
                if line.startswith("Version"):
                    dep_node.version = line.split(":", 1)[1].strip()
                elif line.startswith("Description"):
                    desc = line.split(":", 1)[1].strip()
                    if desc:
                        dep_node.version = f"{dep_node.version} — {desc}" if dep_node.version else desc
        else:
            # Check if it's in official repos (even if not installed)
            search_res = safe_run(
                [pacman, "-Si", dep_name], timeout=5,
            )
            if search_res.returncode != 0:
                dep_node.is_foreign = True

    return graph


def _build_from_pkginfo(pkg_path: Path, graph: DepGraph) -> DepGraph:
    """Build graph from .PKGINFO inside a .pkg.tar.zst."""
    try:
        res = safe_run(
            ["tar", "xf", str(pkg_path), "-O", ".PKGINFO"], timeout=30,
        )
        if res.returncode != 0:
            return graph

        for line in res.stdout.splitlines():
            if line.startswith("pkgname = "):
                graph.root = line.split("=", 1)[1].strip()
            elif line.startswith("pkgver = "):
                graph.nodes[graph.root] = DepNode(
                    name=graph.root,
                    version=line.split("=", 1)[1].strip(),
                    is_installed=False,
                )
            elif line.startswith("depend = "):
                dep_entry = line.split("=", 1)[1].strip()
                dep_name = _parse_dep_name(dep_entry)
                if dep_name:
                    graph.add_edge(graph.root, dep_name)
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.debug("Pacman veritabani okunamadi, grafik kismi kalir: %s", exc)

    return graph


def _extract_for_graph(pkg_path: Path, tmp: Path) -> bool:
    """Paketi tmp icine cikarir; format desteklenmiyorsa False doner."""
    # .pkg.tar.zst once denenir; aksi halde ham tar olarak denenir.
    res = safe_run(
        ["tar", "xf", str(pkg_path), "-C", str(tmp)], timeout=30,
    )
    return res.returncode == 0


def _graph_elf_candidates(tmp: Path) -> list[Path]:
    """Bilinen metin/arsiv uzantilarini ve gizli dosyalari haric tutar."""
    skip_exts = {
        ".py", ".txt", ".conf", ".json", ".xml", ".png", ".jpg", ".svg",
        ".md", ".rst", ".html", ".css", ".js", ".ts", ".yaml", ".yml",
        ".toml", ".ini", ".cfg", ".sh", ".bash", ".desktop", ".service",
        ".1", ".5", ".8", ".man", ".gz", ".xz", ".zst", ".bz2",
    }
    candidates: list[Path] = []
    for c in sorted(tmp.rglob("*")):
        if not c.is_file():
            continue
        if c.suffix.lower() in skip_exts:
            continue
        if c.name.startswith(".") or c.name.startswith("_"):
            continue
        candidates.append(c)
    return candidates


def _ldd_graph_edges(
    candidate: Path, ldd: str, tmp: Path, graph: DepGraph,
) -> None:
    """Tek ikilinin ldd ciktisini graf kenarlarina cevirir.

    'not found' kutuphaneleri de kenar olarak eklenir (is_installed=False)
    boylece eksik bagimlilik graf uzerinde gorunur kalir.
    """
    try:
        ldd_res = safe_run(
            [ldd, str(candidate)], timeout=5,
        )
        if ldd_res.returncode not in (0, 1):  # ldd returns 1 for some binaries
            return
        rel_path = str(candidate.relative_to(tmp))
        for line in ldd_res.stdout.splitlines():
            line = line.strip()
            if "=>" not in line:
                continue
            parts = line.split("=>")
            if len(parts) != 2:
                continue
            lib_name = parts[0].strip()
            lib_path = parts[1].strip().split("(")[0].strip()
            if not lib_name or lib_name in ("linux-vdso.so.1", "ld-linux-x86-64.so.2"):
                continue
            graph.add_edge(rel_path, lib_name)
            graph.nodes[lib_name].is_installed = bool(lib_path) and lib_path != "not found"
    except (subprocess.TimeoutExpired, OSError):
        return


def build_file_dep_graph(pkg_path: Path) -> DepGraph:
    """Build a shared library dependency graph from a package file.

    Extracts the package, identifies ELF binaries using file(1) or magic
    bytes, and maps them to their shared library dependencies via ldd.

    Args:
        pkg_path: Path to .pkg.tar.zst or .deb file.

    Returns:
        DepGraph with binary → library edges.
    """
    graph = DepGraph()
    # Derive the package name via the authoritative extractor, which handles
    # .deb (underscore), .rpm (dot-separated arch), and .pkg.tar.* (hyphens)
    # naming. Using stem.split(".")[0] would break on dotted versions
    # (hello-1.0.0-1-x86_64 -> "hello-1") and miss RPM dot-arch entirely.
    graph.root = extract_package_name(pkg_path.name)

    if not pkg_path.is_file():
        graph.warnings.append(tr("depgraph.dosya_bulunamadi_graph_root", graph_root=graph.root))
        return graph

    with tempfile.TemporaryDirectory(prefix="pkgforge_graph_") as tmpdir:
        tmp = Path(tmpdir)

        if not _extract_for_graph(pkg_path, tmp):
            graph.warnings.append("Paket çıkarılamadı — format desteklenmiyor")
            return graph

        ldd = shutil.which("ldd")
        if not ldd:
            graph.warnings.append("ldd bulunamadı — paylaşılan kütüphane analizi yapılamıyor")
            return graph

        elf_count = 0
        for candidate in _graph_elf_candidates(tmp):
            if not _is_elf_binary(candidate):
                continue
            elf_count += 1
            _ldd_graph_edges(candidate, ldd, tmp, graph)

        if elf_count == 0:
            graph.warnings.append("Pakette ELF dosyası bulunamadı — paylaşılan kütüphane grafiği boş")

    return graph
