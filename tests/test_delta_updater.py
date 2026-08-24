"""Faz 5 (F5.16) — delta guncellemeler (xdelta3, DENEYSEL)."""
from __future__ import annotations

import shutil

import pytest

from core import delta_updater as DU


def test_is_xdelta3_available_returns_bool():
    assert isinstance(DU.is_xdelta3_available(), bool)


def test_get_auto_update_status_has_experimental_fields():
    st = DU.get_auto_update_status()
    assert st["experimental"] is True
    assert "xdelta3_available" in st
    assert "experimental_note" in st
    # Varsayilan olarak kapali:
    assert st["installed"] in (True, False)


def test_create_delta_graceful_without_xdelta3(monkeypatch, tmp_path):
    monkeypatch.setattr(DU, "is_xdelta3_available", lambda: False)
    old = tmp_path / "old.bin"
    new = tmp_path / "new.bin"
    old.write_bytes(b"a" * 100)
    new.write_bytes(b"a" * 100 + b"b")
    out = DU.create_delta(old, new, tmp_path / "d.xdelta")
    assert out is False


def test_apply_delta_graceful_without_xdelta3(monkeypatch, tmp_path):
    monkeypatch.setattr(DU, "is_xdelta3_available", lambda: False)
    out = DU.apply_delta(tmp_path / "old", tmp_path / "d", tmp_path / "o")
    assert out is False


@pytest.mark.skipif(not shutil.which("xdelta3"), reason="xdelta3 kurulu degil")
def test_create_apply_delta_roundtrip(tmp_path):
    old = tmp_path / "old.bin"
    new = tmp_path / "new.bin"
    old.write_bytes(b"PkgForge delta ornek icerik " * 50)
    new.write_bytes(b"PkgForge delta ornek icerik " * 50 + b"EK")
    delta = tmp_path / "d.xdelta"
    assert DU.create_delta(old, new, delta) is True
    assert delta.is_file()
    restored = tmp_path / "restored.bin"
    assert DU.apply_delta(old, delta, restored) is True
    assert restored.read_bytes() == new.read_bytes()
