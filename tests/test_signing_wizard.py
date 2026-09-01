"""Tur-55 B7: Sigstore/PGP onboarding wizard."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.signing_wizard import (
    render_text,
    run_wizard,
)


def test_run_wizard_pgp_steps() -> None:
    """PGP method returns at least the gen-key + export steps."""
    r = run_wizard(method="pgp")
    assert r.method == "pgp"
    assert any("gpg --full-generate-key" in s.command for s in r.steps)
    assert any("--export" in s.command for s in r.steps)
    assert r.config_path == ""  # no persist


def test_run_wizard_sigstore_steps() -> None:
    """Sigstore method returns cosign install + sign-blob steps."""
    r = run_wizard(method="sigstore")
    assert r.method == "sigstore"
    assert any("cosign" in s.command for s in r.steps)
    assert any("sign-blob" in s.command for s in r.steps)


def test_run_wizard_skip() -> None:
    """Skip method returns exactly one 'no signing' step."""
    r = run_wizard(method="skip")
    assert r.method == "skip"
    assert len(r.steps) == 1
    assert "disabled" in r.steps[0].title.lower() or "skip" in r.steps[0].title.lower()


def test_run_wizard_auto_picks_available() -> None:
    """auto picks PGP when gpg is available, else sigstore, else skip."""
    env = r_env()
    gpg_ok = env["gpg"]["available"]
    cosign_ok = env["sigstore"]["cosign_available"]
    expected = "pgp" if gpg_ok else ("sigstore" if cosign_ok else "skip")
    r = run_wizard(method="auto")
    assert r.method == expected


def test_run_wizard_unknown_method_raises() -> None:
    """Unknown method must raise ValueError, not silently coerce."""
    with pytest.raises(ValueError):
        run_wizard(method="quantum")  # type: ignore[arg-type]


def test_run_wizard_persists_config(tmp_path: Path) -> None:
    """Persisted JSON contains method, tools_available, steps, config_path."""
    cfg = tmp_path / "sig.json"
    r = run_wizard(method="pgp", persist_to=cfg)
    assert cfg.is_file()
    assert r.config_path == str(cfg)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["method"] == "pgp"
    assert "tools_available" in data
    assert isinstance(data["steps"], list)
    assert all("order" in s and "title" in s and "command" in s
               for s in data["steps"])


def test_render_text_human() -> None:
    """render_text produces welcome banner + method + all steps."""
    r = run_wizard(method="pgp")
    out = render_text(r)
    assert "Wizard" in out
    assert "Yöntem: pgp" in out or "Method: pgp" in out
    for s in r.steps:
        assert s.title in out
        assert s.command in out


def test_wizardresult_to_dict() -> None:
    """WizardResult.to_dict serializes steps as dicts (not objects)."""
    r = run_wizard(method="sigstore")
    d = r.to_dict()
    assert d["method"] == "sigstore"
    assert isinstance(d["steps"], list)
    assert all(isinstance(s, dict) for s in d["steps"])


# ---- helpers ---------------------------------------------------------------

def r_env() -> dict:
    """Re-read the same env snapshot the wizard sees."""
    return run_wizard(method="skip").tools_available
