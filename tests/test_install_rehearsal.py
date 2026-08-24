"""Faz 5 (F5.14) — kurulum provasi (konteyner ici simulasyon)."""
from __future__ import annotations

import pytest

from core import install_rehearsal as IR


def test_find_runtime_returns_known_or_none():
    rt = IR.find_rehearsal_runtime()
    assert rt is None or rt in IR._RUNTIMES


def test_rehearse_missing_package(tmp_path):
    out = IR.rehearse_install(tmp_path / "nope.pkg.tar.zst")
    assert out["ok"] is False
    assert out["available"] is False
    assert "bulunamadi" in out["reason"]


def test_rehearse_no_runtime_graceful(tmp_path, monkeypatch):
    pkg = tmp_path / "x.pkg.tar.zst"
    pkg.write_bytes(b"fake")
    monkeypatch.setattr(IR, "find_rehearsal_runtime", lambda: None)
    out = IR.rehearse_install(pkg)
    assert out["ok"] is False
    assert out["available"] is False
    assert out["runtime"] is None
    assert "hint" in out


def test_rehearse_distrobox_returns_hint(tmp_path, monkeypatch):
    pkg = tmp_path / "x.pkg.tar.zst"
    pkg.write_bytes(b"fake")
    monkeypatch.setattr(IR, "find_rehearsal_runtime", lambda: "distrobox")
    out = IR.rehearse_install(pkg)
    assert out["available"] is True
    assert out["runtime"] == "distrobox"
    assert out["ok"] is False  # distrobox elle prova gerektirir
    assert out["file_count"] == 0


def test_rpc_install_rehearse_requires_path():
    import core.api_server as A

    with pytest.raises(ValueError):
        A.handle_install_rehearse({})


def test_rpc_install_rehearse_missing_file(tmp_path):
    import core.api_server as A

    out = A.handle_install_rehearse(
        {"package_path": str(tmp_path / "gone.pkg.tar.zst")})
    assert out["ok"] is False
    assert out["available"] is False
