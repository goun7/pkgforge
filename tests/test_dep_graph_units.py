"""Coverage itmesi — core/dep_graph.py saf mantik birimleri."""
from __future__ import annotations

from core.dep_graph import DepGraph, DepNode, _parse_dep_name


def test_add_edge_creates_nodes_and_links():
    g = DepGraph()
    g.add_edge("app", "liba")
    g.add_edge("app", "liba")  # tekrar eklenmez
    assert set(g.nodes) == {"app", "liba"}
    assert g.nodes["app"].deps == ["liba"]
    assert g.nodes["liba"].needed_by == ["app"]


def test_to_mermaid_renders_versions_and_missing():
    g = DepGraph()
    g.add_edge("app-bin", "lib.a.so")
    g.nodes["app-bin"].version = "1.0"
    g.nodes["app-bin"].is_installed = True
    out = g.to_mermaid()
    q = chr(34)
    assert out.startswith("graph TD")
    assert "app_bin[" + q + "app-bin v1.0" + q + "]" in out
    assert "{{" + q + "lib.a.so" + q + "}}" in out
    assert "app_bin --> lib_a_so" in out


def test_to_ascii_tree_with_depth():
    g = DepGraph()
    g.root = "app"
    g.add_edge("app", "liba")
    g.add_edge("liba", "libc")
    g.nodes["app"].is_installed = True
    g.nodes["liba"].is_installed = True
    g.nodes["libc"].is_installed = True
    out = g.to_ascii()
    assert "app" in out and "liba" in out and "libc" in out
    assert "MISSING" not in out


def test_to_ascii_flags_missing_and_circular():
    g = DepGraph()
    g.root = "app"
    g.add_edge("app", "liba")
    g.add_edge("liba", "app")  # dongu
    out = g.to_ascii()
    assert "MISSING" in out
    assert "circular ref" in out


def test_stats_and_max_depth():
    g = DepGraph()
    g.root = "app"
    g.add_edge("app", "liba")
    g.add_edge("liba", "libc")
    g.nodes["app"].is_installed = True
    g.nodes["liba"].is_installed = True
    g.nodes["liba"].is_foreign = True
    s = g.stats()
    assert s["total"] == 3
    assert s["installed"] == 2
    assert s["missing"] == 1
    assert s["foreign"] == 1
    assert s["max_depth"] == 3


def test_max_depth_zero_without_root():
    g = DepGraph()
    g.add_edge("a", "b")
    assert g._max_depth() == 0
    assert DepGraph().stats()["max_depth"] == 0


def test_parse_dep_name_strips_constraints():
    assert _parse_dep_name("foo>=2.0") == "foo"
    assert _parse_dep_name("bar<=1") == "bar"
    assert _parse_dep_name("baz=3") == "baz"
    assert _parse_dep_name("qux>1") == "qux"
    assert _parse_dep_name("q<2") == "q"
    assert _parse_dep_name("sade") == "sade"


def test_dep_node_defaults():
    n = DepNode(name="x")
    assert n.version == ""
    assert n.deps == [] and n.needed_by == []
    assert not n.is_installed and not n.is_foreign