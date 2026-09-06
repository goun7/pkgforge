"""SEC contract tests for core.package_signing hardening."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace as NS

import pytest


def test_passphrase_never_in_argv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """The passphrase must go via stdin (passphrase-fd 0), never argv."""
    import core.package_signing as ps

    pkg = tmp_path / "x.pkg.tar.zst"
    pkg.write_bytes(b"P")
    monkeypatch.setattr(ps, "is_gpg_available", lambda: True)

    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = list(cmd)
        captured["input"] = kw.get("input")
        (tmp_path / "x.pkg.tar.zst.sig").write_bytes(b"S")
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ps, "safe_run", fake_run)

    ok, _msg = ps.sign_package(pkg, passphrase="s3cret")
    assert ok is True
    joined = " ".join(captured["cmd"])
    assert "s3cret" not in joined
    assert "--passphrase-fd" in joined and "0" in joined
    assert captured["input"] == "s3cret"


def test_gnupghome_rejects_foreign_ownership(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import core.package_signing as ps

    home = tmp_path / "gnupg"
    home.mkdir()
    monkeypatch.setattr(ps, "_GNUPGHOME", str(home))
    monkeypatch.setattr(ps.os, "geteuid", lambda: 12345)
    # is_dir de mock'lanir: 3.12 ile 3.14'te pathlib.Path.is_dir()
    # stat'e farkli ic yoldan ulasir; mock'suz dal is_dir'e takilabilir.
    monkeypatch.setattr(ps.Path, "is_dir", lambda self: True)
    monkeypatch.setattr(
        ps.Path, "stat", lambda self, **k: NS(st_uid=999, st_mode=0o700),
        raising=False)
    with pytest.raises(RuntimeError, match="not owned"):
        ps._gpg_homedir_args()


def test_gnupghome_tightens_loose_mode(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import core.package_signing as ps

    home = tmp_path / "gnupg"
    home.mkdir()
    home.chmod(0o755)
    monkeypatch.setattr(ps, "_GNUPGHOME", str(home))
    monkeypatch.setattr(ps.os, "geteuid", lambda: os.stat(tmp_path).st_uid)

    args = ps._gpg_homedir_args()

    assert args == ["--homedir", str(home)]
    assert (home.stat().st_mode & 0o777) == 0o700


def test_gnupghome_missing_dir_returns_empty(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import core.package_signing as ps

    monkeypatch.setattr(ps, "_GNUPGHOME", str(tmp_path / "yok"))
    assert ps._gpg_homedir_args() == []
