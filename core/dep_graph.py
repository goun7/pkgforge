"""PkgForge — Dependency Graph Visualization.

Generates text-based dependency graphs for converted packages using
Mermaid syntax.  Can output to terminal, file, or Mermaid diagram format.

Usage:
    pkgforge graph <package>          # Show dependency graph
    pkgforge graph <package> --file   # Show file dependency graph
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
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
            # Node styling
            safe_name = name.replace("-", "_").replace(".", "_")
            label = name
            if node.version:
                label += f" v{node.version}"
            if node.is_installed:
                lines.append(f"    {safe_name}[\"{label}\"]")
            else:
                lines.append(f"    {safe_name}{{\"{label}\"}}")

            for dep in node.deps:
                dep_safe = dep.replace("-", "_").replace(".", "_")
                lines.append(f"    {safe_name} --> {dep_safe}")

        return "\n".join(lines)

    def to_ascii(self) -> str:
        """Render as simple ASCII tree."""
        if not self.root:
            root = next(iter(self.nodes)) if self.nodes else ""
        else:
            root = self.root

        lines = []
        visited = set()

        def _draw(name: str, prefix: str = "", is_last: bool = True) -> None:
            if name in visited:
                lines.append(f"{prefix}{'└── ' if is_last else '├── '}{name} (↑)")
                return
            visited.add(name)

            node = self.nodes.get(name, DepNode(name=name))
            connector = "└── " if is_last else "├── "
            suffix = ""
            if node.version:
                suffix = f" v{node.version}"
            if not node.is_installed:
                suffix += " ⚠️"
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
        if not self.root:
            return 0

        visited = set()

        def _depth(name: str) -> int:
            if name in visited or name not in self.nodes:
                return 0
            visited.add(name)
            node = self.nodes[name]
            if not node.deps:
                return 1
            return 1 + max(_depth(d) for d in node.deps)

        depth = _depth(self.root)
        return depth


def build_dep_graph(pkg_path: Path) -> DepGraph:
    """Build a dependency graph from a converted .pkg.tar.zst file.

    Uses pacman to query the package's dependencies and checks
    which ones are installed on the system.
    """
    graph = DepGraph()
    pacman = shutil.which("pacman")
    if not pacman:
        log.warning("pacman bulunamadı — grafik oluşturulamıyor")
        return graph

    pkg_name = pkg_path.stem.split("-")[0]
    # Handle .pkg.tar.zst naming
    for part in pkg_path.stem.split("-"):
        if part.startswith("pkg.tar"):
            break
        pkg_name = part
    graph.root = pkg_name

    # Query package dependencies
    res = subprocess.run(
        [pacman, "-Qi", pkg_name],
        capture_output=True, text=True, timeout=10,
    )
    if res.returncode != 0:
        # Not installed, try to read from the file directly
        return graph

    for line in res.stdout.splitlines():
        if line.startswith("Depends On"):
            deps_str = line.split(":", 1)[1].strip()
            if deps_str and deps_str != "None":
                for dep_entry in deps_str.split():
                    dep_name = dep_entry.split(">=")[0].split("<=")[0].split("=")[0]
                    dep_name = dep_entry.split(">")[0].split("<")[0].split("=")[0]
                    if dep_name and dep_name != "None":
                        graph.add_edge(pkg_name, dep_name)
                        # Check if installed
                        dep_res = subprocess.run(
                            [pacman, "-Qi", dep_name],
                            capture_output=True, text=True, timeout=5,
                        )
                        if dep_res.returncode == 0:
                            graph.nodes[dep_name].is_installed = True
                            for line2 in dep_res.stdout.splitlines():
                                if line2.startswith("Version"):
                                    graph.nodes[dep_name].version = line2.split(":", 1)[1].strip()
    return graph


def build_file_dep_graph(pkg_path: Path) -> DepGraph:
    """Build a shared library dependency graph.

    Scans ELF binaries in the package and maps them to their
    shared library dependencies (ldd output).
    """
    graph = DepGraph()
    pkg_name = pkg_path.stem.split(".")[0]
    graph.root = pkg_name

    if not pkg_path.is_file():
        return graph

    # Try to extract and scan shared libs
    import tempfile
    with tempfile.TemporaryDirectory(prefix="pkgforge_graph_") as tmpdir:
        tmp = Path(tmpdir)
        # Try extracting
        res = subprocess.run(
            ["tar", "xf", str(pkg_path), "-C", str(tmp)],
            capture_output=True, timeout=30,
        )
        if res.returncode != 0:
            return graph

        # Find ELF binaries
        ldd = shutil.which("ldd")
        if not ldd:
            return graph

        for elf in tmp.rglob("*"):
            if elf.is_file() and not elf.suffix in (".py", ".txt", ".conf", ".json", ".xml", ".png", ".jpg"):
                try:
                    res = subprocess.run(
                        [ldd, str(elf)],
                        capture_output=True, text=True, timeout=5,
                    )
                    if res.returncode == 0:
                        rel_path = str(elf.relative_to(tmp))
                        for line in res.stdout.splitlines():
                            line = line.strip()
                            if "=>" in line:
                                parts = line.split("=>")
                                if len(parts) == 2:
                                    lib_name = parts[0].strip()
                                    lib_path = parts[1].strip().split("(")[0].strip()
                                    if lib_path and lib_path != "not found":
                                        graph.add_edge(rel_path, lib_name)
                                        graph.nodes[lib_name].is_installed = True
                                    else:
                                        graph.add_edge(rel_path, lib_name)
                except (subprocess.TimeoutExpired, OSError):
                    continue

    return graph
