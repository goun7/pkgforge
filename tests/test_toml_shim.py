"""Tests for the tomllib compatibility shim."""

from __future__ import annotations

import pytest

from core import _toml


def test_loads_parses_basic_table():
    data = _toml.loads('name = "pkgforge"\n[tool]\ncoverage = 99\n')
    assert data["name"] == "pkgforge"
    assert data["tool"]["coverage"] == 99


def test_loads_raises_tomldecodeerror_on_bad_input():
    with pytest.raises(_toml.TOMLDecodeError):
        _toml.loads("not [ valid toml ==")


def test_workspace_uses_shim_and_parses_repo_file():
    from core.workspace import Workspace

    ws = Workspace()
    assert "core" in {m.name for m in ws.members()}
