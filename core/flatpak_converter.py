"""PkgForge — Flatpak to DEB Converter.

Converts a Flatpak application into a .deb package by:
1. Exporting the Flatpak app files from the local repo
2. Packaging them into a standard .deb archive structure
3. Generating a proper DEBIAN/control file

This enables bidirectional package conversion:
- DEB/RPM → Arch (existing)
- Flatpak → DEB (new)

Usage:
    pkgforge flatpak-export <app-id>    # Export to .deb
    pkgforge flatpak-export --list      # List installed apps
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.security import safe_run
from i18n import tr

log = logging.getLogger(__name__)


@dataclass
class FlatpakApp:
    """Metadata about an installed Flatpak application."""

    app_id: str
    name: str
    version: str
    branch: str
    description: str = ""
    origin: str = ""


def is_flatpak_available() -> bool:
    """Return True if flatpak CLI is installed."""
    return shutil.which("flatpak") is not None


def list_installed_apps() -> list[FlatpakApp]:
    """List all installed Flatpak applications."""
    if not is_flatpak_available():
        return []

    # flatpak list --columns=application,name,version,branch,description,origin
    res = safe_run(
        [
            "flatpak", "list",
            "--columns=application,name,version,branch,description,origin",
        ],
        timeout=10,
    )

    apps = []
    if res.returncode == 0:
        for line in res.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 4 and parts[0]:
                apps.append(FlatpakApp(
                    app_id=parts[0],
                    name=parts[1] or parts[0],
                    version=parts[2] or "1.0",
                    branch=parts[3] or "stable",
                    description=parts[4] if len(parts) > 4 else "",
                    origin=parts[5] if len(parts) > 5 else "",
                ))
    return apps


def get_app_info(app_id: str) -> FlatpakApp | None:
    """Get metadata for a specific Flatpak app."""
    apps = list_installed_apps()
    for app in apps:
        if app.app_id == app_id:
            return app
    return None


def export_app_files(
    app_id: str,
    export_dir: Path,
    branch: str = "stable",
) -> bool:
    """Export Flatpak app files to a directory.

    Uses ``flatpak build-export`` to extract the app's files.
    """
    if not is_flatpak_available():
        return False

    # First, get the app's installation path
    # flatpak info --installation=... <app-id>
    res = safe_run(
        ["flatpak", "info", "--show-location", f"{app_id}//{branch}"],
        timeout=10,
    )
    if res.returncode != 0:
        log.warning(tr("flatpak.flatpak_app_bulunamadi_s_s"), app_id, branch)
        return False

    app_path = Path(res.stdout.strip())
    if not app_path.is_dir():
        log.warning(tr("flatpak.flatpak_app_yolu_bulunamadi_s"), app_path)
        return False

    # Copy the app files to the export directory
    export_dir.mkdir(parents=True, exist_ok=True)

    # The app files are typically in: <app_path>/files/
    files_dir = app_path / "files"
    if files_dir.is_dir():
        shutil.copytree(files_dir, export_dir / "opt" / app_id, dirs_exist_ok=True)
    else:
        # Fallback: copy everything
        shutil.copytree(app_path, export_dir / "opt" / app_id, dirs_exist_ok=True)

    log.info(tr("flatpak.flatpak_dosyalari_disa_aktarildi_s"), app_id, export_dir)
    return True


def create_deb_package(
    app: FlatpakApp,
    files_dir: Path,
    output_path: Path,
) -> tuple[bool, str]:
    """Create a .deb package from exported Flatpak files.

    Args:
        app: FlatpakApp metadata.
        files_dir: Directory containing the exported files.
        output_path: Where to write the .deb file.

    Returns:
        (success, message)
    """
    if not files_dir.is_dir():
        return False, tr("flatpak.dosya_dizini_bulunamadi_files", files_dir=files_dir)

    with tempfile.TemporaryDirectory(prefix="pkgforge_deb_") as tmpdir:
        deb_root = Path(tmpdir) / "deb"
        deb_root.mkdir()

        # DEBIAN/control directory
        debian_dir = deb_root / "DEBIAN"
        debian_dir.mkdir()

        # Copy the app files into /opt/<app-id>/
        opt_dir = deb_root / "opt" / app.app_id
        shutil.copytree(files_dir, opt_dir, dirs_exist_ok=True)

        # Generate DEBIAN/control
        arch = "amd64"  # Flatpak apps are typically x86_64
        control = (
            f"Package: {app.app_id.lower().replace('.', '-').replace('_', '-')}\n"
            f"Version: {app.version}\n"
            f"Architecture: {arch}\n"
            f"Maintainer: PkgForge <noreply@pkgforge.app>\n"
            f"Description: {app.name} (converted from Flatpak)\n"
            f" {app.description or app.name}\n"
            f"Installed-Size: {_estimate_size_mb(deb_root)}\n"
        )
        (debian_dir / "control").write_text(control, encoding="utf-8")

        # Generate DEBIAN/postinst for desktop file creation
        postinst = (
            "#!/bin/bash\n"
            "# Flatpak-to-DEB post-installation script\n"
            "set -e\n"
            f"echo \"Installed {app.name} from Flatpak export\"\n"
        )
        postinst_path = debian_dir / "postinst"
        postinst_path.write_text(postinst, encoding="utf-8")
        postinst_path.chmod(0o755)

        # Build .deb using dpkg-deb
        dpkg_deb = shutil.which("dpkg-deb")
        if not dpkg_deb:
            return False, "dpkg-deb bulunamadı — dpkg paketi gerekli"

        res = safe_run(
            ["dpkg-deb", "--build", str(deb_root), str(output_path)],
            timeout=60,
        )

        if res.returncode != 0:
            return False, tr("flatpak.dpkg_deb_basarisiz_res", res_stderr=res.stderr)

        log.info(tr("flatpak.deb_paketi_olusturuldu_s"), output_path)
        return True, tr("flatpak.deb_paketi_hazir_output", output_path_name=output_path.name)


def flatpak_to_deb(
    app_id: str,
    output_dir: Path,
    branch: str = "stable",
) -> tuple[bool, str, Path | None]:
    """Convert a Flatpak app to a .deb package.

    Args:
        app_id: Flatpak application ID (e.g., "org.mozilla.firefox").
        output_dir: Directory to write the .deb file.
        branch: Flatpak branch (default: "stable").

    Returns:
        (success, message, deb_path)
    """
    if not is_flatpak_available():
        return False, "flatpak bulunamadı — pacman -S flatpak", None

    # Get app metadata
    app = get_app_info(app_id)
    if not app:
        return False, tr("flatpak.flatpak_uygulamasi_bulunamadi_app_2", app_id=app_id), None

    output_dir.mkdir(parents=True, exist_ok=True)
    deb_name = f"{app.app_id.lower().replace('.', '-').replace('_', '-')}_{app.version}_amd64.deb"
    output_path = output_dir / deb_name

    with tempfile.TemporaryDirectory(prefix="pkgforge_flatpak_") as tmpdir:
        files_dir = Path(tmpdir) / "files"

        # Export files
        if not export_app_files(app_id, files_dir, branch):
            return False, tr("flatpak.flatpak_dosyalari_disa_aktarilamadi", app_id=app_id), None

        # Create .deb
        ok, msg = create_deb_package(app, files_dir, output_path)
        if ok:
            return True, msg, output_path
        return False, msg, None


def _estimate_size_mb(directory: Path) -> int:
    """Estimate directory size in MB.

    Okunamayan girdiler boyuta 0 olarak katilir ve debug loglanir; hata
    tum tahmini degil, yalnizca o girdiyi etkiler.
    """
    total = 0
    skipped = 0
    for f in directory.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            skipped += 1
    if skipped:
        log.debug(
            "Boyut tahmini: %d okunamayan girdi atlandi (%s)",
            skipped, directory,
        )
    return max(1, total // (1024 * 1024))


# ── Flatpak Runtime Image Export ─────────────────────────────────

def export_flatpak_runtime(
    app_id: str,
    output_dir: Path,
    branch: str = "stable",
    sdk: str = "org.freedesktop.Platform",
    sdk_version: str = "24.08",
) -> tuple[bool, str, Path | None]:
    """Export a Flatpak app as a runtime image (JSON manifest).

    Generates a Flatpak manifest that can be used with `flatpak-builder`
    to rebuild the app from its exported files.

    Args:
        app_id: Flatpak application ID (e.g., "org.mozilla.firefox").
        output_dir: Directory to write the manifest.
        branch: Flatpak branch (default "stable").
        sdk: SDK runtime to use (default "org.freedesktop.Platform").
        sdk_version: SDK version (default "24.08").

    Returns:
        (success, message, manifest_path)
    """
    if not is_flatpak_available():
        return False, "flatpak bulunamadı", None

    # Get app info
    apps = list_installed_apps()
    app = None
    for a in apps:
        if a.app_id == app_id:
            app = a
            break

    if not app:
        return False, tr("flatpak.flatpak_uygulamasi_bulunamadi_app", app_id=app_id), None

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate manifest
    manifest = {
        "app-id": app.app_id,
        "runtime": sdk,
        "runtime-version": sdk_version,
        "sdk": f"{sdk}.Sdk",
        "command": app.app_id.split(".")[-1],
        "finish-args": [
            "--share=ipc",
            "--socket=x11",
            "--socket=wayland",
            "--socket=pulseaudio",
            "--share=network",
        ],
        "modules": [
            {
                "name": app.app_id.split(".")[-1],
                "buildsystem": "simple",
                "build-commands": [
                    "cp -r /app/* ${FLATPAK_DEST}/",
                ],
                "sources": [
                    {
                        "type": "flatpak",
                        "url": f"https://dl.flathub.org/repo/appstream/{app.app_id}.flatpakref",
                        "branch": branch,
                    }
                ],
            }
        ],
        # PkgForge metadata
        "_pkgforge": {
            "source": "pkgforge flatpak-export --to-flatpak-runtime",
            "original_version": app.version,
            "original_branch": app.branch,
            "description": app.description,
        },
    }

    manifest_name = f"{app.app_id.lower().replace('.', '-')}.json"
    manifest_path = output_dir / manifest_name
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    msg = (
        tr("flatpak.flatpak_runtime_manifest_olusturuld", app_name=app.name, app_version=app.version, sdk=sdk, sdk_version=sdk_version, manifest_path=manifest_path, manifest_path_2=manifest_path)
    )
    return True, msg, manifest_path
