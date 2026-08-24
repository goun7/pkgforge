"""PkgForge — Binary Differential Updates.

When downloading a new version of a package that we already have locally,
compute a binary delta (xdelta3) so only the diff needs to be downloaded.
This can reduce bandwidth by 80-95% for point releases.

Requires ``xdelta3`` to be installed (pacman -S xdelta3).
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from config import extract_package_name
from core.security import safe_run

log = logging.getLogger(__name__)


def is_xdelta3_available() -> bool:
    """Return True if xdelta3 is installed."""
    return shutil.which("xdelta3") is not None


def create_delta(old_file: Path, new_file: Path, delta_file: Path) -> bool:
    """Create a binary delta from old_file to new_file.

    Args:
        old_file: The current/old version of the file.
        new_file: The new version of the file.
        delta_file: Output path for the delta.

    Returns:
        True if delta was created successfully.
    """
    if not is_xdelta3_available():
        log.warning("xdelta3 bulunamadı — delta oluşturulamıyor")
        return False

    if not old_file.is_file() or not new_file.is_file():
        return False

    res = safe_run(
        ["xdelta3", "-e", "-f", "-s", str(old_file), str(new_file), str(delta_file)],
        timeout=300,
    )

    if res.returncode != 0:
        log.warning("xdelta3 delta oluşturma başarısız (kod %d): %s",
                    res.returncode, res.stderr[:200])
        return False

    new_size = new_file.stat().st_size
    delta_size = delta_file.stat().st_size
    ratio = (1 - delta_size / new_size) * 100 if new_size > 0 else 0

    log.info("Delta oluşturuldu: %s → %s (%d bayt, %.0f%% tasarruf)",
             old_file.name, delta_file.name, delta_size, ratio)
    return True


def apply_delta(old_file: Path, delta_file: Path, output_file: Path) -> bool:
    """Apply a binary delta to reconstruct the new file.

    Args:
        old_file: The current/old version of the file.
        delta_file: The delta file to apply.
        output_file: Output path for the reconstructed file.

    Returns:
        True if delta was applied successfully.
    """
    if not is_xdelta3_available():
        return False

    if not old_file.is_file() or not delta_file.is_file():
        return False

    res = safe_run(
        ["xdelta3", "-d", "-f", "-s", str(old_file), str(delta_file), str(output_file)],
        timeout=300,
    )

    if res.returncode != 0:
        log.warning("xdelta3 delta uygulama başarısız (kod %d): %s",
                    res.returncode, res.stderr[:200])
        return False

    log.info("Delta uygulandı: %s + %s → %s",
             old_file.name, delta_file.name, output_file.name)
    return True


def find_local_previous(package_name: str, pkg_dir: Path | None = None) -> Path | None:
    """Search for a previously downloaded version of the same package.

    Looks in the conversion history backups and the specified directory.
    """
    if pkg_dir is None:
        from config import CONFIG_DIR
        pkg_dir = CONFIG_DIR / "backups"

    if not pkg_dir.is_dir():
        return None

    # Search for matching package files (same base name, different version)
    candidates: list[Path] = []
    for f in pkg_dir.iterdir():
        if not f.is_file():
            continue
        if ".pkg.tar" in f.name and not f.name.endswith((".sig", ".json")):
            # Match by the full clean package name. Using split("-")[0]
            # truncated hyphenated names (my-cool-app -> "my") and the
            # substring check over-matched unrelated packages.
            base = extract_package_name(f.name)
            if base and base.lower() == package_name.lower():
                candidates.append(f)

    # Return the most recent one (by modification time)
    if candidates:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]

    return None


def download_with_delta(
    url: str,
    dest_file: Path,
    old_file: Path | None = None,
    *,
    require_https: bool = True,
) -> tuple[Path, bool]:
    """Download a file using delta if a local previous version exists.

    Args:
        url: Direct download URL.
        dest_file: Where to save the final file.
        old_file: Previous version (if available locally).
        require_https: Require HTTPS.

    Returns:
        (final_path, used_delta)
    """
    from core.downloader import download_package

    if old_file is None or not old_file.is_file() or not is_xdelta3_available():
        # No delta possible — full download
        result = download_package(url, dest_file.parent, require_https=require_https)
        return result, False

    # Try to download delta first (URL pattern: same URL + .xdelta suffix)
    delta_url = url + ".xdelta"
    with tempfile.TemporaryDirectory(prefix="pkgforge_delta_") as tmpdir:
        delta_file = Path(tmpdir) / "delta.xdelta"

        try:
            download_package(delta_url, Path(tmpdir),
                           require_https=require_https)
            # If we got here, delta was downloaded
            if apply_delta(old_file, delta_file, dest_file):
                log.info("Delta indirme başarılı: %s", dest_file.name)
                return dest_file, True
        except Exception as exc:  # noqa: BLE001
            log.info("Delta indirilemedi, tam dosya indiriliyor: %s (%s)", url, exc)

    # Fallback to full download
    result = download_package(url, dest_file.parent, require_https=require_https)
    return result, False


# ── Auto-Update Daemon ───────────────────────────────────────────

_SERVICE_NAME = "pkgforge-auto-update"
_TIMER_NAME = "pkgforge-auto-update"


def install_auto_update(interval_hours: int = 6) -> tuple[bool, str]:
    """Install a systemd timer that periodically checks for updates.

    Args:
        interval_hours: How often to check (default: every 6 hours).

    Returns:
        (success, message)
    """
    import os

    # Check for systemd
    systemctl = None
    for path in ["/usr/bin/systemctl", "/bin/systemctl", "/usr/sbin/systemctl"]:
        if os.path.isfile(path):
            systemctl = path
            break
    if not systemctl:
        return False, "systemctl bulunamadı — systemd kurulu değil"

    # Generate check script
    script_content = """#!/bin/bash
# PkgForge Auto-Update Check
# Checks for upstream updates and optionally downloads with delta
# Generated by PkgForge — do not edit manually

set -euo pipefail

LOG_FILE="/var/log/pkgforge-auto-update.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Starting auto-update check" >> "$LOG_FILE" 2>/dev/null || true

# Run the check (non-interactive, stdout to log)
pkgforge check-updates >> "$LOG_FILE" 2>&1 || true

echo "[$TIMESTAMP] Auto-update check complete" >> "$LOG_FILE" 2>/dev/null || true
"""
    script_path = Path("/usr/local/bin/pkgforge-auto-update.sh")

    # Service unit
    service_content = """[Unit]
Description=PkgForge Auto-Update Check
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/pkgforge-auto-update.sh
User=root
StandardOutput=journal
StandardError=journal
"""

    # Timer unit
    timer_content = f"""[Unit]
Description=PkgForge Auto-Update Timer (every {interval_hours}h)

[Timer]
OnCalendar=*-*-* 00/6:00:00
RandomizedDelaySec=1800
Persistent=true

[Install]
WantedBy=timers.target
"""

    service_path = Path(f"/etc/systemd/system/{_SERVICE_NAME}.service")
    timer_path = Path(f"/etc/systemd/system/{_TIMER_NAME}.timer")

    try:
        from core.privileged import privileged_chmod_argv, privileged_write_argv
        from core.security import safe_run as _safe_run

        # Script
        res = _safe_run(privileged_write_argv("pkexec", str(script_path)),
                        input=script_content, timeout=10)
        if res.returncode != 0:
            return False, "Script dosyası yazılamadı"
        _safe_run(privileged_chmod_argv("pkexec", "755", str(script_path)),
                    timeout=5)

        # Service
        res = _safe_run(privileged_write_argv("pkexec", str(service_path)),
                        input=service_content, timeout=10)
        if res.returncode != 0:
            return False, "Service dosyası yazılamadı"

        # Timer
        res = _safe_run(privileged_write_argv("pkexec", str(timer_path)),
                        input=timer_content, timeout=10)
        if res.returncode != 0:
            return False, "Timer dosyası yazılamadı"

        # Enable
        _safe_run([systemctl, "daemon-reload"], timeout=10)
        _safe_run([systemctl, "enable", f"{_TIMER_NAME}.timer"], timeout=10)
        _safe_run([systemctl, "start", f"{_TIMER_NAME}.timer"], timeout=10)

        msg = (
            f"✅ Auto-update servisi kuruldu!\n\n"
            f"  Timer: Her {interval_hours} saatte bir kontrol\n"
            f"  Servis: {_SERVICE_NAME}.service\n"
            f"  Timer: {_TIMER_NAME}.timer\n\n"
            f"  Durum: systemctl status {_TIMER_NAME}.timer\n"
            f"  Durdur: sudo systemctl stop {_TIMER_NAME}.timer\n"
            f"  Kaldır: pkgforge auto-update --remove"
        )
        return True, msg

    except Exception as exc:  # noqa: BLE001
        return False, f"Kurulum başarısız: {exc}"


def remove_auto_update() -> tuple[bool, str]:
    """Remove the auto-update systemd timer and service."""
    import os

    systemctl = None
    for path in ["/usr/bin/systemctl", "/bin/systemctl", "/usr/sbin/systemctl"]:
        if os.path.isfile(path):
            systemctl = path
            break
    if not systemctl:
        return False, "systemctl bulunamadı"

    try:
        from core.privileged import privileged_remove_argv
        from core.security import safe_run as _safe_run

        _safe_run([systemctl, "stop", f"{_TIMER_NAME}.timer"], timeout=10)
        _safe_run([systemctl, "disable", f"{_TIMER_NAME}.timer"], timeout=10)

        for p in [
            f"/etc/systemd/system/{_SERVICE_NAME}.service",
            f"/etc/systemd/system/{_TIMER_NAME}.timer",
            "/usr/local/bin/pkgforge-auto-update.sh",
        ]:
            if Path(p).exists():
                _safe_run(privileged_remove_argv("pkexec", p), timeout=10)

        _safe_run([systemctl, "daemon-reload"], timeout=10)
        return True, "✅ Auto-update servisi kaldırıldı."

    except Exception as exc:  # noqa: BLE001
        return False, f"Kaldırma başarısız: {exc}"


def get_auto_update_status() -> dict:
    """Get current auto-update service status."""
    import os

    systemctl = None
    for path in ["/usr/bin/systemctl", "/bin/systemctl", "/usr/sbin/systemctl"]:
        if os.path.isfile(path):
            systemctl = path
            break

    status = {"installed": False, "active": False, "next_run": ""}

    if not systemctl:
        return status

    from core.security import safe_run as _safe_run

    res = _safe_run([systemctl, "is-enabled", f"{_TIMER_NAME}.timer"], timeout=5)
    status["installed"] = res.returncode == 0

    if status["installed"]:
        res = _safe_run([systemctl, "is-active", f"{_TIMER_NAME}.timer"], timeout=5)
        status["active"] = res.returncode == 0

        res = _safe_run([systemctl, "show", f"{_TIMER_NAME}.timer",
                         "--property=NextElapseUSecRealtime"], timeout=5)
        if res.returncode == 0 and "=" in res.stdout:
            status["next_run"] = res.stdout.split("=", 1)[1].strip()

    return status


def enable_auto_update() -> tuple[bool, str]:
    """Enable the auto-update systemd timer.

    Returns:
        (success, message)
    """
    from core.security import safe_run as _safe_run
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return False, "systemctl bulunamadı — systemd kurulu değil"

    timer_path = Path(f"/etc/systemd/system/{_TIMER_NAME}.timer")
    if not timer_path.exists():
        return False, f"Timer dosyası bulunamadı: {timer_path}"

    res = _safe_run([systemctl, "enable", f"{_TIMER_NAME}.timer"], timeout=10)
    if res.returncode != 0:
        return False, f"Timer etkinleştirilemedi: {res.stderr[:200]}"

    res = _safe_run([systemctl, "start", f"{_TIMER_NAME}.timer"], timeout=10)
    if res.returncode != 0:
        return False, f"Timer başlatılamadı: {res.stderr[:200]}"

    return True, f"Otomatik güncelleme etkinleştirildi ({_TIMER_NAME}.timer)"


def disable_auto_update() -> tuple[bool, str]:
    """Disable the auto-update systemd timer.

    Returns:
        (success, message)
    """
    from core.security import safe_run as _safe_run
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return False, "systemctl bulunamadı — systemd kurulu değil"

    _safe_run([systemctl, "stop", f"{_TIMER_NAME}.timer"], timeout=10)
    res = _safe_run([systemctl, "disable", f"{_TIMER_NAME}.timer"], timeout=10)

    if res.returncode == 0:
        return True, f"Otomatik güncelleme devre dışı bırakıldı ({_TIMER_NAME}.timer)"
    else:
        return False, f"Timer devre dışı bırakılamadı: {res.stderr[:200]}"


def get_delta_logs(lines: int = 50) -> str:
    """Read recent logs from the delta auto-update service.

    Args:
        lines: Number of log lines to read.

    Returns:
        Log output as string.
    """
    from core.security import safe_run as _safe_run

    systemctl = shutil.which("systemctl")
    if not systemctl:
        return "systemctl bulunamadı"

    res = _safe_run(
        ["journalctl", "-u", f"{_SERVICE_NAME}", "-n", str(lines), "--no-pager"],
        timeout=10,
    )
    if res.returncode == 0:
        stdout = res.stdout if isinstance(res.stdout, str) else res.stdout.decode("utf-8", errors="replace")
        return stdout.strip()
    else:
        return f"Log okunamadı: {res.stderr[:200]}"


def notify_update_available(packages: list[str]) -> bool:
    """Send desktop notification about available updates.

    Uses notify-send if available, falls back to stdout.

    Args:
        packages: List of package names with available updates.

    Returns:
        True if notification was sent.
    """
    if not packages:
        return False

    message = f"{len(packages)} paket güncellenebilir:\n" + "\n".join(f"  • {p}" for p in packages[:10])

    # Try notify-send (Linux desktop)
    notify_send = shutil.which("notify-send")
    if notify_send:
        from core.security import safe_run as _safe_run
        _safe_run(
            [notify_send, "--urgency=normal", "PkgForge Güncelleme", message],
            timeout=5,
        )
        log.info("Desktop notification gönderildi: %d paket", len(packages))
        return True

    # Fallback: stdout
    print(f"\n📢 Güncelleme Mevcut:\n{message}")
    return True
