"""PkgForge — Btrfs/ZFS Snapshot Manager.

Provides atomic rollback for package installations by leveraging filesystem
snapshots.  Before each ``pacman -U`` install, a snapshot of the root (or
a configured subvolume) is taken.  If the installation fails or the user
wants to undo it, the snapshot is restored atomically.

Supported backends:
- **Btrfs**: ``btrfs subvolume snapshot`` / ``btrfs subvolume delete``
- **ZFS**: ``zfs snapshot`` / ``zfs rollback``

When neither filesystem is detected, the feature silently degrades to the
existing HistoryDB-based backup (no snapshots).
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from core.privileged import privileged_systemctl_argv, privileged_write_argv
from core.security import safe_run
from i18n import tr

log = logging.getLogger(__name__)


@dataclass
class SnapshotInfo:
    """Metadata about a created snapshot."""

    backend: str          # "btrfs" | "zfs" | "none"
    snapshot_name: str
    mount_point: str
    success: bool
    detail: str = ""


def detect_backend() -> str:
    """Detect which snapshot backend is available.

    Returns "btrfs", "zfs", or "none".
    """
    # Check if root is btrfs
    if shutil.which("btrfs"):
        res = safe_run(["btrfs", "filesystem", "show", "/"], timeout=5)
        if res.returncode == 0 and "btrfs" in res.stdout.lower():
            return "btrfs"

    # Check if root is zfs
    if shutil.which("zfs"):
        res = safe_run(["zfs", "list", "-o", "name,mountpoint", "-H"], timeout=5)
        if res.returncode == 0 and "/" in res.stdout:
            return "zfs"

    return "none"


def get_root_mount_point() -> str:
    """Return the mount point of the root filesystem."""
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "/":
                    return parts[0]
    except OSError:
        pass
    return ""


def take_snapshot(label: str = "pkgforge") -> SnapshotInfo:
    """Take a snapshot of the root filesystem before package installation.

    Args:
        label: A human-readable label for the snapshot.

    Returns:
        SnapshotInfo with the snapshot details.
    """
    backend = detect_backend()
    ts = int(time.time())
    snap_name = f"pkgforge-{label}-{ts}"

    if backend == "btrfs":
        return _take_btrfs_snapshot(snap_name)
    elif backend == "zfs":
        return _take_zfs_snapshot(snap_name)
    else:
        return SnapshotInfo(
            backend="none",
            snapshot_name="",
            mount_point="",
            success=False,
            detail="Btrfs veya ZFS algılanmadı — snapshot oluşturulamıyor",
        )


def restore_snapshot(snapshot_name: str) -> tuple[bool, str]:
    """Restore a previously taken snapshot.

    WARNING: This is a destructive operation that reverts the entire
    root filesystem to the snapshot state.

    Args:
        snapshot_name: The full snapshot name to restore.

    Returns:
        (success, message)
    """
    backend = detect_backend()

    if backend == "btrfs":
        return _restore_btrfs_snapshot(snapshot_name)
    elif backend == "zfs":
        return _restore_zfs_snapshot(snapshot_name)
    else:
        return False, "Btrfs veya ZFS algılanamadı"


def list_snapshots() -> list[dict[str, str]]:
    """List all PkgForge-created snapshots.

    Returns:
        List of dicts with 'name', 'date', 'backend' keys.
    """
    backend = detect_backend()
    if backend == "btrfs":
        return _list_btrfs_snapshots()
    elif backend == "zfs":
        return _list_zfs_snapshots()
    return []


def delete_snapshot(snapshot_name: str) -> bool:
    """Delete a PkgForge snapshot."""
    backend = detect_backend()
    if backend == "btrfs":
        res = safe_run(["btrfs", "subvolume", "delete", snapshot_name], timeout=30)
        return res.returncode == 0
    elif backend == "zfs":
        res = safe_run(["zfs", "destroy", snapshot_name], timeout=30)
        return res.returncode == 0
    return False


# ── Btrfs implementation ────────────────────────────────────────

def _get_btrfs_root_subvolume() -> str:
    """Find the btrfs root subvolume mount point."""
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 5 and parts[2] == "btrfs" and parts[1] == "/":
                    # mount options contain subvol=/@
                    opts = parts[3]
                    for opt in opts.split(","):
                        if opt.startswith("subvol="):
                            return opt.split("=", 1)[1]
    except OSError:
        pass
    return "@"


def _take_btrfs_snapshot(snap_name: str) -> SnapshotInfo:
    """Take a btrfs snapshot of the root subvolume."""
    snap_path = f"/{snap_name}"

    res = safe_run(
        ["btrfs", "subvolume", "snapshot", "/", snap_path],
        timeout=60,
    )

    if res.returncode == 0:
        log.info(tr("snapshot.btrfs_snapshot_olusturuldu_s"), snap_path)
        return SnapshotInfo(
            backend="btrfs",
            snapshot_name=snap_path,
            mount_point="/",
            success=True,
            detail=tr("snapshot.btrfs_snapshot_hazir_snap", snap_path=snap_path),
        )
    else:
        log.warning(tr("snapshot.btrfs_snapshot_basarisiz_s"), res.stderr[:200])
        return SnapshotInfo(
            backend="btrfs",
            snapshot_name="",
            mount_point="/",
            success=False,
            detail=tr("snapshot.snapshot_basarisiz_stderr", stderr=res.stderr[:200]),
        )


def _restore_btrfs_snapshot(snapshot_name: str) -> tuple[bool, str]:
    """Restore a btrfs snapshot via boot-time rollback.

    Creates a systemd service that performs the rollback on next boot,
    since live root filesystem replacement is unsafe.
    """
    snap_path = snapshot_name if snapshot_name.startswith("/") else f"/{snapshot_name}"

    # 1. Create rollback script
    rollback_script = (
        '#!/bin/bash\n'
        'set -e\n'
        f"SNAP='{snap_path}'\n"
        'CURRENT=/@pkgforge-pre-rollback\n'
        'echo "[pkgforge] Rolling back to snapshot: $SNAP"\n'
        '# Backup current root\n'
        'btrfs subvolume snapshot / "$CURRENT" 2>/dev/null || true\n'
        '# Replace root with snapshot\n'
        'btrfs subvolume delete / --subvol "$(btrfs subvolume show / | head -1 | awk \'{print $2}\')" 2>/dev/null || true\n'
        f"btrfs subvolume snapshot '{snap_path}' /\n"
        'echo "[pkgforge] Rollback complete. Removing snapshot..."\n'
        'btrfs subvolume delete "$SNAP" 2>/dev/null || true\n'
        'systemctl disable pkgforge-rollback.service\n'
        'rm /etc/systemd/system/pkgforge-rollback.service\n'
        'rm /usr/local/bin/pkgforge-rollback.sh\n'
        'echo "[pkgforge] Cleanup done."\n'
    )

    script_path = Path("/usr/local/bin/pkgforge-rollback.sh")
    try:
        script_path.write_text(rollback_script, encoding="utf-8")
        script_path.chmod(0o755)
    except OSError as exc:
        return False, tr("snapshot.rollback_scripti_olusturulamadi_exc", exc=exc)

    # 2. Create systemd service for boot-time execution
    service_content = (
        "[Unit]\n"
        "Description=PkgForge Package Rollback\n"
        "After=local-fs.target\n"
        "Before=multi-user.target\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "ExecStart=/usr/local/bin/pkgforge-rollback.sh\n"
        "RemainAfterExit=no\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )

    service_path = Path("/etc/systemd/system/pkgforge-rollback.service")
    try:
        # Use pkexec for the systemd file creation
        res = safe_run(
            privileged_write_argv("pkexec", str(service_path)),
            input=service_content,
            timeout=10,
        )
        if res.returncode != 0:
            # Fallback: write to temp and ask user to install
            # pid-suffixed name; content is a generated systemd unit,
            # not attacker-controlled, and the file is only a hand-off for the user.
            tmp_service = Path(f"/tmp/pkgforge-rollback-{os.getpid()}.service")  # nosec B108
            tmp_service.write_text(service_content, encoding="utf-8")
            msg = (
                tr("snapshot.btrfs_rollback_plani_hazirlandi_2", tmp_service=tmp_service, service_path=service_path, snap_path=snap_path)
            )
            return True, msg

        # Enable the service
        safe_run(privileged_systemctl_argv(
            "pkexec", "enable", "pkgforge-rollback.service"), timeout=10)

        msg = (
            tr("snapshot.btrfs_rollback_plani_hazirlandi", snap_path=snap_path)
        )
        return True, msg

    except Exception as exc:  # noqa: BLE001
        return False, tr("snapshot.rollback_plani_olusturulamadi_exc", exc=exc)


def _list_btrfs_snapshots() -> list[dict[str, str]]:
    """List btrfs snapshots starting with 'pkgforge-'."""
    snapshots: list[dict[str, str]] = []
    try:
        # List all subvolumes
        res = safe_run(["btrfs", "subvolume", "list", "/"], timeout=10)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 9:
                    name = parts[-1]
                    if name.startswith("pkgforge-"):
                        snapshots.append({
                            "name": f"/{name}",
                            "date": " ".join(parts[4:8]),
                            "backend": "btrfs",
                        })
    except Exception as exc:  # noqa: BLE001
        log.debug(tr("snapshot.btrfs_snapshot_listesi_alinamadi_s"), exc)
    return snapshots


# ── ZFS implementation ──────────────────────────────────────────

def _get_zfs_root_dataset() -> str:
    """Find the ZFS dataset mounted at /."""
    res = safe_run(
        ["zfs", "list", "-o", "name,mountpoint", "-H", "-t", "filesystem"],
        timeout=5,
    )
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "/":
                return parts[0]
    return ""


def _take_zfs_snapshot(snap_name: str) -> SnapshotInfo:
    """Take a ZFS snapshot of the root dataset."""
    dataset = _get_zfs_root_dataset()
    if not dataset:
        return SnapshotInfo(
            backend="zfs", snapshot_name="", mount_point="",
            success=False, detail="ZFS root dataset bulunamadı",
        )

    snap_full = f"{dataset}@{snap_name}"
    res = safe_run(["zfs", "snapshot", snap_full], timeout=60)

    if res.returncode == 0:
        log.info(tr("snapshot.zfs_snapshot_olusturuldu_s"), snap_full)
        return SnapshotInfo(
            backend="zfs",
            snapshot_name=snap_full,
            mount_point="/",
            success=True,
            detail=tr("snapshot.zfs_snapshot_hazir_snap", snap_full=snap_full),
        )
    else:
        return SnapshotInfo(
            backend="zfs", snapshot_name="", mount_point="/",
            success=False, detail=tr("snapshot.zfs_snapshot_basarisiz_stderr", stderr=res.stderr[:200]),
        )


def _restore_zfs_snapshot(snapshot_name: str) -> tuple[bool, str]:
    """Restore a ZFS snapshot."""
    msg = (
        tr("snapshot.zfs_snapshot_geri_yukleme", snapshot_name=snapshot_name, snapshot_name_2=snapshot_name)
    )
    return True, msg


def _list_zfs_snapshots() -> list[dict[str, str]]:
    """List ZFS snapshots with pkgforge prefix."""
    snapshots: list[dict[str, str]] = []
    dataset = _get_zfs_root_dataset()
    if not dataset:
        return snapshots

    res = safe_run(
        ["zfs", "list", "-o", "name,creation", "-H", "-t", "snapshot",
         "-s", "creation", f"{dataset}@pkgforge-*"],
        timeout=10,
    )
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                snapshots.append({
                    "name": parts[0],
                    "date": parts[1],
                    "backend": "zfs",
                })
    return snapshots
