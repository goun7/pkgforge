"""Faz 5 (F5.18) — fleet sync backend soyutlamasi + age sifreleme."""
from __future__ import annotations

import pytest

from core import sync_backends as SB


def test_backends_registry():
    assert SB.BACKENDS == ("webdav", "git", "rclone-s3")


def test_age_available_returns_bool():
    assert isinstance(SB.age_available(), bool)


def test_get_backend_git():
    b = SB.get_backend("git", repo_url="https://x/repo.git", branch="main")
    assert isinstance(b, SB.GitBackend)
    assert b.repo_url == "https://x/repo.git"
    assert b.name == "git"


def test_get_backend_rclone():
    b = SB.get_backend("rclone-s3", remote="s3:bucket/prefix/")
    assert isinstance(b, SB.RcloneBackend)
    assert b.remote == "s3:bucket/prefix"


def test_get_backend_unknown_raises():
    with pytest.raises(SB.SyncBackendError):
        SB.get_backend("ftp")


def test_get_backend_webdav_delegates_to_cloud_sync():
    with pytest.raises(SB.SyncBackendError) as ei:
        SB.get_backend("webdav")
    assert "cloud_sync" in str(ei.value)


def test_git_backend_unavailable_without_url():
    b = SB.GitBackend("")
    assert b.is_available() is False
    with pytest.raises(SB.SyncBackendError):
        b.push(b"x", "bundle.zip")


def test_rclone_backend_unavailable_without_remote():
    b = SB.RcloneBackend("")
    assert b.is_available() is False
    with pytest.raises(SB.SyncBackendError):
        b.pull("bundle.zip")


def test_age_encrypt_requires_recipient():
    if not SB.age_available():
        pytest.skip("age kurulu degil")
    with pytest.raises(SB.SyncBackendError):
        SB.age_encrypt(b"data", "")


def test_age_decrypt_missing_identity(tmp_path):
    if not SB.age_available():
        pytest.skip("age kurulu degil")
    with pytest.raises(SB.SyncBackendError):
        SB.age_decrypt(b"data", tmp_path / "nope.key")


def test_base_backend_not_implemented():
    b = SB.SyncBackend()
    with pytest.raises(NotImplementedError):
        b.push(b"x", "n")
    with pytest.raises(NotImplementedError):
        b.pull("n")
