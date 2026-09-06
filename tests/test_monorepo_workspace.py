"""Tur-55 C9: monorepo workspace introspection."""
from __future__ import annotations

from pathlib import Path

from core.workspace import Workspace


def test_workspace_lists_members() -> None:
    w = Workspace()
    names = {m.name for m in w.members()}
    assert "core" in names
    assert "desktop" in names
    assert "shared" in names


def test_workspace_get_known_member() -> None:
    w = Workspace()
    core = w.get("core")
    assert core is not None
    assert core.language == "python"
    assert "3.10+" in core.runtime
    assert core.path.endswith("core")


def test_workspace_get_unknown_returns_none() -> None:
    w = Workspace()
    assert w.get("does-not-exist") is None


def test_workspace_to_dict_shape() -> None:
    w = Workspace()
    d = w.to_dict()
    assert "core" in d
    assert d["core"]["language"] == "python"
    assert "desktop" in d


def test_workspace_missing_file_returns_empty(tmp_path: Path, monkeypatch) -> None:
    # Workspace without workspace.toml → empty, no crash.
    import core.workspace as mod

    # monkeypatch ile: test bitince orijinal WORKSPACE_FILE geri gelir;
    # ham atama sonraki testlerin Workspace() cagrilarini zehirlerdi.
    monkeypatch.setattr(mod, "WORKSPACE_FILE", tmp_path / "nope.toml")
    w = mod.Workspace()
    assert w.members() == []
    assert w.to_dict() == {}
