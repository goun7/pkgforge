"""Coverage itmesi — core/sync_backends.py uctan-uca (yerel git repo)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core import sync_backends as SB


def _git(cmd):
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def _make_origin(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(["git", "init", "-q", "-b", "main", str(seed)])
    (seed / "readme.txt").write_text("x")
    _git(["git", "-C", str(seed), "add", "."])
    _git(["git", "-C", str(seed), "-c", "user.email=t@t.local",
          "-c", "user.name=T", "commit", "-qm", "seed"])
    origin = tmp_path / "origin.git"
    _git(["git", "clone", "-q", "--bare", "--no-hardlinks",
          str(seed), str(origin)])
    return origin


def test_git_backend_push_pull_roundtrip(tmp_path):
    origin = _make_origin(tmp_path)
    b = SB.GitBackend(repo_url=origin.as_uri(), branch="main")
    assert b.is_available()
    blob = b"pkgforge-bundle-icerigi"
    out = b.push(blob, "bundle.zip")
    assert out == {"ok": True, "backend": "git", "size": len(blob)}
    assert b.pull("bundle.zip") == blob


def test_git_backend_push_overwrites_and_pulls_newest(tmp_path):
    origin = _make_origin(tmp_path)
    b = SB.GitBackend(repo_url=origin.as_uri(), branch="main")
    b.push(b"v1", "bundle.zip")
    b.push(b"v2-daha-yeni", "bundle.zip")
    assert b.pull("bundle.zip") == b"v2-daha-yeni"


def test_git_backend_pull_missing_remote_file(tmp_path):
    origin = _make_origin(tmp_path)
    b = SB.GitBackend(repo_url=origin.as_uri(), branch="main")
    with pytest.raises(SB.SyncBackendError):
        b.pull("yok.zip")


def test_rclone_push_builds_remote_path(monkeypatch):
    seen = {}

    def fake_run(cmd):
        seen["cmd"] = list(cmd)

    monkeypatch.setattr(SB, "_run", fake_run)
    monkeypatch.setattr(SB.shutil, "which", lambda *_a, **_k: "/usr/bin/rclone")
    b = SB.get_backend("rclone-s3", remote="s3:kova/onetki/")
    out = b.push(b"veri", "bundle.zip")
    assert out["backend"] == "rclone-s3"
    assert seen["cmd"][0] == "rclone"
    assert seen["cmd"][-1] == "s3:kova/onetki/bundle.zip"


def test_rclone_pull_reads_tempfile(monkeypatch, tmp_path):
    def fake_run(cmd):
        Path(cmd[3]).write_bytes(b"uzaktan-gelen")

    monkeypatch.setattr(SB, "_run", fake_run)
    monkeypatch.setattr(SB.shutil, "which", lambda *_a, **_k: "/usr/bin/rclone")
    b = SB.RcloneBackend("s3:kova")
    assert b.pull("bundle.zip") == b"uzaktan-gelen"