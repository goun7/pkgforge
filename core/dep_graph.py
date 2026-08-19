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
        res = subprocess.run(
            [file_cmd, "--brief", str(file_path)],
            capture_output=True, text=True, timeout=5,
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

    # Extract package name from filename or use as-is
    pkg_name = pkg_path.stem
    if ".pkg.tar" in pkg_name:
        # Filename like: package-1.0.0-1-x86_64.pkg.tar.zst
        pkg_name = "-".join(pkg_name.split("-")[:-3])  # Remove version-rel-arch

    graph.root = pkg_name

    # Query package dependencies
    res = subprocess.run(
        [pacman, "-Qi", pkg_name],
        capture_output=True, text=True, timeout=10,
    )
    if res.returncode != 0:
        graph.warnings.append(
            f"'{pkg_name}' kurulu değil. Grafik için paketin kurulu olması veya "
            f".pkg.tar.zst dosyasının mevcut olması gerekir."
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
        dep_res = subprocess.run(
            [pacman, "-Qi", dep_name],
            capture_output=True, text=True, timeout=5,
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
            search_res = subprocess.run(
                [pacman, "-Si", dep_name],
                capture_output=True, text=True, timeout=5,
            )
            if search_res.returncode != 0:
                dep_node.is_foreign = True

    return graph


def _build_from_pkginfo(pkg_path: Path, graph: DepGraph) -> DepGraph:
    """Build graph from .PKGINFO inside a .pkg.tar.zst."""
    try:
        res = subprocess.run(
            ["tar", "xf", str(pkg_path), "-O", ".PKGINFO"],
            capture_output=True, text=True, timeout=30,
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
    except (subprocess.TimeoutExpired, OSError):
        pass

    return graph


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
    pkg_name = pkg_path.stem.split(".")[0]
    graph.root = pkg_name

    if not pkg_path.is_file():
        graph.warnings.append(f"Dosya bulunamadı: {pkg_name}")
        return graph

    with tempfile.TemporaryDirectory(prefix="pkgforge_graph_") as tmpdir:
        tmp = Path(tmpdir)

        # Try extracting — try .pkg.tar.zst first, then raw tar
        extract_ok = False
        if ".pkg.tar" in pkg_path.name:
            res = subprocess.run(
                ["tar", "xf", str(pkg_path), "-C", str(tmp)],
                capture_output=True, timeout=30,
            )
            extract_ok = res.returncode == 0
        else:
            res = subprocess.run(
                ["tar", "xf", str(pkg_path), "-C", str(tmp)],
                capture_output=True, timeout=30,
            )
            extract_ok = res.returncode == 0

        if not extract_ok:
            graph.warnings.append("Paket çıkarılamadı — format desteklenmiyor")
            return graph

        # Find ELF binaries properly
        ldd = shutil.which("ldd")
        if not ldd:
            graph.warnings.append("ldd bulunamadı — paylaşılan kütüphane analizi yapılamıyor")
            return graph

        elf_count = 0
        for candidate in sorted(tmp.rglob("*")):
            if not candidate.is_file():
                continue
            # Skip known non-binary extensions
            skip_exts = {
                ".py", ".txt", ".conf", ".json", ".xml", ".png", ".jpg", ".svg",
                ".md", ".rst", ".html", ".css", ".js", ".ts", ".yaml", ".yml",
                ".toml", ".ini", ".cfg", ".sh", ".bash", ".desktop", ".service",
                ".1", ".5", ".8", ".man", ".gz", ".xz", ".zst", ".bz2",
            }
            if candidate.suffix.lower() in skip_exts:
                continue
            # Skip directories and hidden files
            if candidate.name.startswith(".") or candidate.name.startswith("_"):
                continue

            if not _is_elf_binary(candidate):
                continue

            elf_count += 1
            try:
                ldd_res = subprocess.run(
                    [ldd, str(candidate)],
                    capture_output=True, text=True, timeout=5,
                )
                if ldd_res.returncode in (0, 1):  # ldd returns 1 for some binaries
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
                        if lib_path and lib_path != "not found":
                            graph.add_edge(rel_path, lib_name)
                            graph.nodes[lib_name].is_installed = True
                        else:
                            graph.add_edge(rel_path, lib_name)
                            graph.nodes[lib_name].is_installed = False
            except (subprocess.TimeoutExpired, OSError):
                continue

        if elf_count == 0:
            graph.warnings.append("Pakette ELF dosyası bulunamadı — paylaşılan kütüphane grafiği boş")

    return graph
