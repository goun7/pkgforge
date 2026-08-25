"""Coverage itmesi - core/snapshot_manager.py backend dagitimi ve btrfs."""
from __future__ import annotations

import core.snapshot_manager as SM
from core.snapshot_manager import (
    delete_snapshot,
    detect_backend,
    list_snapshots,
    restore_snapshot,
    take_snapshot,
)


def _ns(code, out="", err=""):
    return SM.SimpleNamespace if False else __import__("types").SimpleNamespace(
        returncode=code, stdout=out, stderr=err)


def test_detect_backend_matrix(monkeypatch):
    monkeypatch.setattr(SM.shutil, "which", lambda n: None)
    assert detect_backend() == "none"

    paths = {"btrfs": "/usr/bin/btrfs"}
    monkeypatch.setattr(SM.shutil, "which", lambda n: paths.get(n))
    monkeypatch.setattr(SM, "safe_run", lambda c, timeout=None: _ns(0, out="Label: none btrfs"))
    assert detect_backend() == "btrfs"
    monkeypatch.setattr(SM, "safe_run", lambda c, timeout=None: _ns(1))
    assert detect_backend() == "none"

    paths = {"zfs": "/usr/sbin/zfs"}
    monkeypatch.setattr(SM.shutil, "which", lambda n: paths.get(n))
    monkeypatch.setattr(SM, "safe_run", lambda c, timeout=None: _ns(0, out="/ rpool/ROOT"))
    assert detect_backend() == "zfs"


def test_take_snapshot_none(monkeypatch):
    monkeypatch.setattr(SM, "detect_backend", lambda: "none")
    info = take_snapshot("deneme")
    assert info.backend == "none" and info.success is False
    assert "algılanmadı" in info.detail


def test_delete_and_restore_dispatch(monkeypatch):
    monkeypatch.setattr(SM, "detect_backend", lambda: "btrfs")
    seen = []
    monkeypatch.setattr(SM, "safe_run", lambda c, timeout=None: seen.append(c) or _ns(0))
    assert delete_snapshot("/pkgforge-x") is True
    assert seen[0][:3] == ["btrfs", "subvolume", "delete"]

    ok, msg = restore_snapshot("x")
    assert isinstance(ok, bool) and isinstance(msg, str)
    monkeypatch.setattr(SM, "detect_backend", lambda: "none")
    ok2, msg2 = restore_snapshot("x")
    assert ok2 is False and "algılanamadı" in msg2
    assert delete_snapshot("/x") is False
    assert list_snapshots() == []


def test_btrfs_take_list(monkeypatch):
    calls = []

    def fake_run(cmd, timeout=None, **kw):
        calls.append(list(cmd))
        if cmd[0] == "btrfs" and cmd[1] == "subvolume" and cmd[2] == "snapshot":
            return _ns(0)
        if cmd[:2] == ["btrfs", "subvolume"] and cmd[2] == "list":
            return _ns(0, out="ID 256 gen top level 5 path subvol1 pkgforge-demo-1000")
        return _ns(0)
    monkeypatch.setattr(SM.shutil, "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(SM, "safe_run", fake_run)
    monkeypatch.setattr(SM, "_get_btrfs_root_subvolume", lambda: "/@")
    info = SM._take_btrfs_snapshot("/@snap-test")
    assert info.success is True and info.backend == "btrfs"
    assert any("snapshot" in c for c in calls)

    snaps = SM._list_btrfs_snapshots()
    assert snaps and snaps[0]["name"].lstrip("/").startswith("pkgforge-")

    ok, msg = SM._restore_btrfs_snapshot("/@snap-test")
    assert isinstance(ok, bool)


def test_zfs_paths(monkeypatch):
    calls = []

    def fake_run(cmd, timeout=None, **kw):
        calls.append(list(cmd))
        if cmd[0] == "zfs" and cmd[1] == "list":
            return _ns(0, out="rpool/ROOT\t/\nrpool/tmp\t/tmp")
        return _ns(0)
    monkeypatch.setattr(SM.shutil, "which", lambda n: "/usr/sbin/" + n)
    monkeypatch.setattr(SM, "safe_run", fake_run)
    ds = SM._get_zfs_root_dataset()
    assert ds.startswith("rpool/")
    info = SM._take_zfs_snapshot("rpool/ROOT@sn")
    assert info.backend == "zfs" and any("snapshot" in c for c in calls)
    lst = SM._list_zfs_snapshots()
    assert isinstance(lst, list)