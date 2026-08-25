"""Coverage itmesi — core/rollback_verify.py dogrulama akislari."""
from __future__ import annotations

from types import SimpleNamespace as NS

import core.rollback_verify as RV


def test_verify_backend_none(monkeypatch):
    monkeypatch.setattr(RV, "detect_backend", lambda: "none")
    r = RV.verify_rollback()
    assert r.verified is False and r.backend == "none"
    assert "algılanmadı" in r.detail


def test_verify_happy_path(monkeypatch):
    monkeypatch.setattr(RV, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(RV, "take_snapshot", lambda name: NS(
        success=True, snapshot_name=name, detail=""))
    monkeypatch.setattr("core.snapshot_manager.list_snapshots",
                        lambda: [{"name": "verify-test"}])
    monkeypatch.setattr(RV, "delete_snapshot", lambda n: True)
    r = RV.verify_rollback()
    assert r.verified is True and r.snapshot_name == "verify-test"
    assert "başarılı" in r.detail and "Temizlendi" in r.detail


def test_verify_snapshot_create_fails(monkeypatch):
    monkeypatch.setattr(RV, "detect_backend", lambda: "zfs")
    monkeypatch.setattr(RV, "take_snapshot", lambda name: NS(
        success=False, snapshot_name="", detail="disk dolu"))
    r = RV.verify_rollback()
    assert r.verified is False and "disk dolu" in r.detail


def test_verify_snapshot_not_listed(monkeypatch):
    monkeypatch.setattr(RV, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(RV, "take_snapshot", lambda name: NS(
        success=True, snapshot_name="gizli-snap", detail=""))
    monkeypatch.setattr("core.snapshot_manager.list_snapshots",
                        list)
    r = RV.verify_rollback()
    assert r.verified is False and "listelenemiyor" in r.detail


def test_verify_delete_failure_still_verified(monkeypatch):
    monkeypatch.setattr(RV, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(RV, "take_snapshot", lambda name: NS(
        success=True, snapshot_name="yapiskan", detail=""))
    monkeypatch.setattr("core.snapshot_manager.list_snapshots",
                        lambda: [{"name": "yapiskan"}])
    monkeypatch.setattr(RV, "delete_snapshot", lambda n: False)
    r = RV.verify_rollback()
    assert r.verified is True and "silinemedi" in r.detail


def test_restore_backend_none_and_snap_fail(monkeypatch):
    monkeypatch.setattr(RV, "detect_backend", lambda: "none")
    r = RV.verify_rollback_restore()
    assert r.verified is False and "algılanmadı" in r.detail

    monkeypatch.setattr(RV, "detect_backend", lambda: "zfs")
    monkeypatch.setattr(RV, "take_snapshot", lambda name: NS(
        success=False, snapshot_name="", detail="hata"))
    r2 = RV.verify_rollback_restore()
    assert r2.verified is False and "hata" in r2.detail


def test_restore_success_state_match(monkeypatch):
    monkeypatch.setattr(RV, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(RV, "take_snapshot", lambda name: NS(
        success=True, snapshot_name="restore-test", detail=""))
    monkeypatch.setattr("core.snapshot_manager.restore_snapshot",
                        lambda name: (True, "tamam"))
    r = RV.verify_rollback_restore()
    assert r.verified is True and "eşleşiyor" in r.detail


def test_restore_fail_and_mismatch(monkeypatch):
    monkeypatch.setattr(RV, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(RV, "take_snapshot", lambda name: NS(
        success=True, snapshot_name="r", detail=""))
    monkeypatch.setattr("core.snapshot_manager.restore_snapshot",
                        lambda name: (False, "izin yok"))
    r = RV.verify_rollback_restore()
    assert r.verified is False and "izin yok" in r.detail

    calls = {"n": 0}

    def fake_hash(root, max_files=100):
        calls["n"] += 1
        return "hash-" + str(calls["n"])
    monkeypatch.setattr(RV, "_hash_file_tree", fake_hash)
    r2 = RV.verify_rollback_restore()
    assert r2.verified is False and calls["n"] == 2
