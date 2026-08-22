"""Tests for dep_graph.DepGraph, aur_publish pure functions, _parse_dep_name.

All hermetic: in-memory graph, temp dirs, and the tracked lictest fixture.
"""

import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LICTEST_PKG = PROJECT_ROOT / "utest" / "lictest" / "lictest-1.0.0-1-any.pkg.tar.zst"


class TestDepGraph(unittest.TestCase):

    def test_add_edge(self):
        from core.dep_graph import DepGraph
        g = DepGraph(root="app")
        g.add_edge("app", "libc")
        g.add_edge("app", "libm")
        self.assertIn("libc", g.nodes["app"].deps)
        self.assertIn("app", g.nodes["libc"].needed_by)

    def test_add_edge_dedup(self):
        from core.dep_graph import DepGraph
        g = DepGraph()
        g.add_edge("a", "b")
        g.add_edge("a", "b")
        self.assertEqual(g.nodes["a"].deps, ["b"])
        self.assertEqual(g.nodes["b"].needed_by, ["a"])

    def test_to_mermaid(self):
        from core.dep_graph import DepGraph
        g = DepGraph(root="my-app")
        g.add_edge("my-app", "libc")
        out = g.to_mermaid()
        self.assertIn("graph TD", out)
        self.assertIn("my_app", out)  # hyphens sanitized
        self.assertIn("-->", out)

    def test_to_ascii(self):
        from core.dep_graph import DepGraph
        g = DepGraph(root="app")
        g.add_edge("app", "libc")
        out = g.to_ascii()
        self.assertIn("app", out)
        self.assertIn("libc", out)

    def test_to_ascii_circular(self):
        from core.dep_graph import DepGraph
        g = DepGraph(root="a")
        g.add_edge("a", "b")
        g.add_edge("b", "a")  # cycle
        out = g.to_ascii()
        self.assertIn("circular", out)

    def test_stats(self):
        from core.dep_graph import DepGraph, DepNode
        g = DepGraph(root="app")
        g.add_edge("app", "libc")
        g.nodes["libc"].is_installed = True
        s = g.stats()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["installed"], 1)
        self.assertEqual(s["missing"], 1)

    def test_max_depth(self):
        from core.dep_graph import DepGraph
        g = DepGraph(root="a")
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        self.assertEqual(g._max_depth(), 3)

    def test_max_depth_empty(self):
        from core.dep_graph import DepGraph
        self.assertEqual(DepGraph()._max_depth(), 0)


class TestParseDepName(unittest.TestCase):

    def test_strips_version_ops(self):
        from core.dep_graph import _parse_dep_name
        self.assertEqual(_parse_dep_name("foo>=2.0"), "foo")
        self.assertEqual(_parse_dep_name("bar<=1.0"), "bar")
        self.assertEqual(_parse_dep_name("baz=3.0"), "baz")
        self.assertEqual(_parse_dep_name("qux>1"), "qux")
        self.assertEqual(_parse_dep_name("quux<2"), "quux")

    def test_plain_name(self):
        from core.dep_graph import _parse_dep_name
        self.assertEqual(_parse_dep_name("glibc"), "glibc")


class TestDetectBuildSystem(unittest.TestCase):

    def _detect(self, filename):
        from core.aur_publish import detect_build_system
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / filename).write_text("")
            return detect_build_system(Path(td))

    def test_cmake(self):
        self.assertEqual(self._detect("CMakeLists.txt"), "cmake")

    def test_meson(self):
        self.assertEqual(self._detect("meson.build"), "meson")

    def test_cargo(self):
        self.assertEqual(self._detect("Cargo.toml"), "cargo")

    def test_python(self):
        self.assertEqual(self._detect("pyproject.toml"), "python")

    def test_go(self):
        self.assertEqual(self._detect("go.mod"), "go")

    def test_unknown(self):
        from core.aur_publish import detect_build_system
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(detect_build_system(Path(td)), "unknown")


@unittest.skipUnless(LICTEST_PKG.is_file(), "lictest fixture missing")
class TestExtractPkgInfo(unittest.TestCase):

    def test_real_package(self):
        from core.aur_publish import _extract_pkg_info
        info = _extract_pkg_info(LICTEST_PKG)
        self.assertEqual(info["name"], "lictest")
        self.assertEqual(info["version"], "1.0.0-1")

    def test_missing_file_falls_back_to_filename(self):
        from core.aur_publish import _extract_pkg_info
        # No real file -> tar fails -> filename fallback
        info = _extract_pkg_info(Path("/tmp/myapp-2.0-3-x86_64.pkg.tar.zst"))
        self.assertEqual(info["name"], "myapp")
        self.assertEqual(info["version"], "2.0-3")


if __name__ == "__main__":
    unittest.main()
