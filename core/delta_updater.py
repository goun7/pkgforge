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
from core.security import safe_run, sha256_hash
from i18n import tr

# NOT: Fonksiyonlar safe_run'a çağrı anında 'from core.security import
# safe_run as _safe_run' ile ulaşır — BİLİNÇLİ geç bağlama. Testler
# core.security.safe_run'ı değiştirebilmelidir; modül seviyesinde tek
# kopya almak bu esnekliği kırar.

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
        log.warning(tr("delta.xdelta3_bulunamadi_delta_olusturulamiyor"))
        return False

    if not old_file.is_file() or not new_file.is_file():
        return False

    res = safe_run(
        ["xdelta3", "-e", "-f", "-s", str(old_file), str(new_file), str(delta_file)],
        timeout=300,
    )

    if res.returncode != 0:
        log.warning(tr("delta.xdelta3_delta_olusturma_basarisiz_kod"),
                    res.returncode, res.stderr[:200])
        return False

    new_size = new_file.stat().st_size
    delta_size = delta_file.stat().st_size
    ratio = (1 - delta_size / new_size) * 100 if new_size > 0 else 0

    log.info(tr("delta.delta_olusturuldu_s_s_d"),
             old_file.name, delta_file.name, delta_size, ratio)
    return True


def apply_delta(
    old_file: Path,
    delta_file: Path,
    output_file: Path,
    *,
    expected_sha256: str | None = None,
) -> bool:
    """Apply a binary delta to reconstruct the new file.

    Args:
        old_file: The current/old version of the file.
        delta_file: The delta file to apply.
        output_file: Output path for the reconstructed file.
        expected_sha256: When provided, the reconstructed file's SHA-256 must
            match (case-insensitive) or the result is discarded and the apply
            is treated as failed. Strongly recommended for remote deltas — a
            delta fetched over the network is untrusted input, and applying it
            without verifying the output hash is a supply-chain risk.

    Returns:
        True if delta was applied successfully (and verified, when a hash is
        supplied).
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
        log.warning(tr("delta.xdelta3_delta_uygulama_basarisiz_kod"),
                    res.returncode, res.stderr[:200])
        return False

    if expected_sha256 is not None:
        actual = sha256_hash(output_file)
        if actual.lower() != expected_sha256.strip().lower():
            log.warning(
                "Delta sha256 doğrulaması başarısız: beklenen %s, alınan %s — "
                "çıktı siliniyor",
                expected_sha256[:16], actual[:16])
            output_file.unlink(missing_ok=True)
            return False

    log.info(tr("delta.delta_uygulandi_s_s_s"),
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
    expected_sha256: str | None = None,
) -> tuple[Path, bool]:
    """Download a file using delta if a local previous version exists.

    Args:
        url: Direct download URL.
        dest_file: Where to save the final file.
        old_file: Previous version (if available locally).
        require_https: Require HTTPS.
        expected_sha256: When supplied, a delta-reconstructed file must match
            this SHA-256 or the delta path is rejected and the full download
            fallback is used. Callers that know the target hash should always
            pass it — remote deltas are untrusted input.

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
            if apply_delta(old_file, delta_file, dest_file,
                           expected_sha256=expected_sha256):
                log.info(tr("delta.delta_indirme_basarili_s"), dest_file.name)
                return dest_file, True
        except Exception as exc:  # noqa: BLE001
            log.info("Delta indirilemedi, tam dosya indiriliyor: %s (%s)", url, exc)

    # Fallback to full download
    result = download_package(url, dest_file.parent, require_https=require_https)
    return result, False


# ── Auto-Update Daemon ───────────────────────────────────────────

_SERVICE_NAME = "pkgforge-auto-update"
_TIMER_NAME = "pkgforge-auto-update"


def _find_systemctl() -> str | None:
    """Bilinen yollar arasindan systemctl'i bulur (yoksa None)."""
    import os
    for path in ["/usr/bin/systemctl", "/bin/systemctl", "/usr/sbin/systemctl"]:
        if os.path.isfile(path):
            return path
    return None


def _auto_update_units(interval_hours: int) -> tuple:
    """Auto-update biriminin (script, service, timer) iceriklerini uretir.

    Timer plani — Faz 14: interval_hours takvime gercek yansir.
    24'un bolenleri OnCalendar saat adimiyla; digerleri OnUnitActiveSec.
    """
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

    hours = max(int(interval_hours), 1)
    if 24 % hours == 0:
        sched = f"OnCalendar=*-*-* 00/{hours}:00:00"
    else:
        sched = f"OnUnitActiveSec={hours}h\nOnBootSec=10min"
    timer_content = f"""[Unit]
Description=PkgForge Auto-Update Timer (every {interval_hours}h)

[Timer]
{sched}
RandomizedDelaySec=1800
Persistent=true

[Install]
WantedBy=timers.target
"""

    service_path = Path(f"/etc/systemd/system/{_SERVICE_NAME}.service")
    timer_path = Path(f"/etc/systemd/system/{_TIMER_NAME}.timer")
    return (
        script_path, script_content,
        service_path, service_content,
        timer_path, timer_content,
    )


def _write_and_enable_units(units: tuple) -> tuple[bool, str]:
    """Unit dosyalarini yazar ve timer'i TEK yetkili diyalogda acar.

    service-deploy: manifest + daemon-reload + enable + start hepsi helper
    icinde. Eski akis 4 ayri pkexec cagrisi yapiyordu.
    """
    script_path, script_content, service_path, service_content, timer_path, timer_content = units
    from core.privileged import (
        build_write_batch_manifest,
        privileged_service_deploy_argv,
    )
    from core.security import safe_run as _safe_run

    manifest = build_write_batch_manifest([
        ("755", str(script_path), script_content),
        ("644", str(service_path), service_content),
        ("644", str(timer_path), timer_content),
    ])
    res = _safe_run(privileged_service_deploy_argv(
        "pkexec", f"{_TIMER_NAME}.timer"), input=manifest, timeout=60)
    if res.returncode != 0:
        return False, tr("delta.dosyalar_yazilamadi_kod_res", res_returncode=res.returncode)
    return True, ""


def install_auto_update(interval_hours: int = 6) -> tuple[bool, str]:
    """Install a systemd timer that periodically checks for updates.

    Args:
        interval_hours: How often to check (default: every 6 hours).

    Returns:
        (success, message)
    """
    if not _find_systemctl():
        return False, "systemctl bulunamadı — systemd kurulu değil"

    units = _auto_update_units(interval_hours)
    try:
        ok, err = _write_and_enable_units(units)
        if not ok:
            return False, err
    except Exception as exc:  # noqa: BLE001
        return False, tr("delta.kurulum_basarisiz_exc", exc=exc)

    NL = chr(10)
    msg = (
        "✅ Auto-update servisi kuruldu!" + NL + NL
        + f"  Timer: Her {interval_hours} saatte bir kontrol" + NL
        + f"  Servis: {_SERVICE_NAME}.service" + NL
        + f"  Timer: {_TIMER_NAME}.timer" + NL + NL
        + f"  Durum: systemctl status {_TIMER_NAME}.timer" + NL
        + "  Kaldır: pkgforge auto-update --remove (GUI'den Updates sayfası da olur)"
    )
    return True, msg


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
        from core.privileged import privileged_service_remove_argv
        from core.security import safe_run as _safe_run

        # Tek pkexec diyalogu: stop + disable + dosya silme + reload.
        res = _safe_run(privileged_service_remove_argv(
            "pkexec", f"{_TIMER_NAME}.timer",
            f"/etc/systemd/system/{_SERVICE_NAME}.service",
            f"/etc/systemd/system/{_TIMER_NAME}.timer",
            "/usr/local/bin/pkgforge-auto-update.sh"), timeout=60)
        if res.returncode != 0:
            return False, tr("delta.kaldirma_basarisiz_exc",
                             exc=f"helper kod {res.returncode}")
        return True, "✅ Auto-update servisi kaldırıldı."

    except Exception as exc:  # noqa: BLE001
        return False, tr("delta.kaldirma_basarisiz_exc", exc=exc)


def get_auto_update_status() -> dict:
    """Get current auto-update service status.

    F5.16: delta guncellemeler DENEYSEL'dir ve varsayilan olarak kapalidir;
    durum ayrica xdelta3'un kurulu olup olmadigini da bildirir.
    """
    import os

    systemctl = None
    for path in ["/usr/bin/systemctl", "/bin/systemctl", "/usr/sbin/systemctl"]:
        if os.path.isfile(path):
            systemctl = path
            break

    status = {
        "installed": False,
        "active": False,
        "next_run": "",
        "xdelta3_available": is_xdelta3_available(),
        "experimental": True,
        "experimental_note": "Delta guncellemeler DENEYSEL ve varsayilan kapali",
    }

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
    from core.privileged import privileged_service_enable_argv
    from core.security import safe_run as _safe_run
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return False, "systemctl bulunamadı — systemd kurulu değil"

    timer_path = Path(f"/etc/systemd/system/{_TIMER_NAME}.timer")
    if not timer_path.exists():
        return False, tr("delta.timer_dosyasi_bulunamadi_timer", timer_path=timer_path)

    # enable + start TEK diyalogda (service-enable).
    res = _safe_run(privileged_service_enable_argv(
        "pkexec", f"{_TIMER_NAME}.timer"), timeout=30)
    if res.returncode != 0:
        return False, tr("delta.timer_etkinlestirilemedi_stderr", stderr=res.stderr[:200])

    return True, tr("delta.otomatik_guncelleme_etkinlestirildi", _TIMER_NAME=_TIMER_NAME)


def disable_auto_update() -> tuple[bool, str]:
    """Disable the auto-update systemd timer.

    Returns:
        (success, message)
    """
    from core.privileged import privileged_service_disable_argv
    from core.security import safe_run as _safe_run
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return False, "systemctl bulunamadı — systemd kurulu değil"

    # stop + disable TEK diyalogda (service-disable).
    res = _safe_run(privileged_service_disable_argv(
        "pkexec", f"{_TIMER_NAME}.timer"), timeout=30)

    if res.returncode == 0:
        return True, tr("delta.otomatik_guncelleme_devre_disi", _TIMER_NAME=_TIMER_NAME)
    else:
        return False, tr("delta.timer_devre_disi_birakilamadi", stderr=res.stderr[:200])


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
        return tr("delta.log_okunamadi_stderr", stderr=res.stderr[:200])


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

    message = tr("delta.packages_paket_guncellenebilir", packages=len(packages)) + "\n".join(f"  • {p}" for p in packages[:10])

    # Try notify-send (Linux desktop)
    notify_send = shutil.which("notify-send")
    if notify_send:
        from core.security import safe_run as _safe_run
        _safe_run(
            [notify_send, "--urgency=normal", "PkgForge Güncelleme", message],
            timeout=5,
        )
        log.info(tr("delta.desktop_notification_gonderildi_d_paket"), len(packages))
        return True

    # Fallback: stdout
    print(tr("delta.guncelleme_mevcut_message", message=message))
    return True
