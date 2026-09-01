"""PkgForge — AppImage to DEB Converter.

Extracts an AppImage (which is a self-mounting squashfs filesystem)
and packages its contents into a standard .deb archive.

AppImages contain:
- /usr/ directory with the application
- Optional .desktop file and icons
- AppRun script (entry point)

The converter extracts these and creates a proper Debian package
with correct directory structure and control file.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.security import safe_run
from i18n import tr

log = logging.getLogger(__name__)


@dataclass
class AppImageInfo:
    """Metadata extracted from an AppImage."""

    name: str = ""
    version: str = ""
    description: str = ""
    author: str = ""
    homepage: str = ""
    desktop_file: str = ""  # Contents of .desktop file


def is_appimage_available() -> bool:
    """Check if we can process AppImages (need unsquashfs or --appimage-extract)."""
    return bool(shutil.which("unsquashfs"))


def is_appimage_file(path: Path) -> bool:
    """Check if a file is an AppImage (magic bytes: 0x41, 0x49, 0x02 = 'AI')"""
    if not path.is_file():
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(3)
            return header == b"AI\x02"
    except OSError:
        return False


def extract_appimage(appimage_path: Path, dest_dir: Path) -> bool:
    """Extract an AppImage to a directory.

    Uses ``--appimage-extract`` flag (built-in extraction) or
    ``unsquashfs`` as fallback.
    """
    if not appimage_path.is_file():
        return False

    # Method 1: AppImage built-in extraction (if executable)
    if os.access(appimage_path, os.X_OK):
        res = safe_run(
            [str(appimage_path), "--appimage-extract"],
            cwd=str(dest_dir),
            timeout=120,
        )
        if res.returncode == 0:
            # AppImage extracts to squashfs-root/
            extracted = dest_dir / "squashfs-root"
            if extracted.is_dir():
                return True

    # Method 2: unsquashfs
    unsquashfs = shutil.which("unsquashfs")
    if unsquashfs:
        res = safe_run(
            [unsquashfs, "-d", str(dest_dir / "squashfs-root"), str(appimage_path)],
            timeout=120,
        )
        return res.returncode == 0

    return False


def parse_desktop_file(desktop_path: Path) -> dict[str, str]:
    """Parse a .desktop file for metadata."""
    info: dict[str, str] = {}
    if not desktop_path.is_file():
        return info

    for line in desktop_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("["):
            key, _, value = line.partition("=")
            info[key.strip()] = value.strip()

    return info


def get_appimage_info(appimage_path: Path) -> AppImageInfo:
    """Extract metadata from an AppImage."""
    info = AppImageInfo()

    with tempfile.TemporaryDirectory(prefix="pkgforge_appimage_") as tmpdir:
        extract_dir = Path(tmpdir)
        if not extract_appimage(appimage_path, extract_dir):
            return info

        approot = extract_dir / "squashfs-root"

        # Find .desktop file
        desktop_files = list(approot.rglob("*.desktop"))
        if desktop_files:
            desktop = parse_desktop_file(desktop_files[0])
            info.name = desktop.get("Name", appimage_path.stem)
            info.version = desktop.get("X-AppImage-Version", "1.0")
            info.description = desktop.get("Comment", desktop.get("GenericName", ""))
            info.author = desktop.get("Author", desktop.get("X-DeveloperName", ""))
            info.homepage = desktop.get("URL", "")
            info.desktop_file = desktop_files[0].read_text(encoding="utf-8", errors="replace")
        else:
            info.name = appimage_path.stem
            info.version = "1.0"

    return info


def appimage_to_deb(
    appimage_path: Path,
    output_dir: Path,
) -> tuple[bool, str, Path | None]:
    """Convert an AppImage to a .deb package.

    Args:
        appimage_path: Path to the .AppImage file.
        output_dir: Directory to write the .deb file.

    Returns:
        (success, message, deb_path)
    """
    if not appimage_path.is_file():
        return False, tr("appimage.dosya_bulunamadi_appimage_path", appimage_path=appimage_path), None

    if not is_appimage_file(appimage_path):
        return False, tr("appimage.gecersiz_appimage_appimage_path", appimage_path_name=appimage_path.name), None

    # Get metadata
    info = get_appimage_info(appimage_path)
    pkg_name = re.sub(r"[^a-z0-9+.-]", "-", info.name.lower().replace(" ", "-"))
    deb_name = f"{pkg_name}_{info.version}_amd64.deb"
    output_path = output_dir / deb_name

    with tempfile.TemporaryDirectory(prefix="pkgforge_appimage_") as tmpdir:
        extract_dir = Path(tmpdir)

        # Extract
        if not extract_appimage(appimage_path, extract_dir):
            return False, "AppImage çıkarılamadı", None

        approot = extract_dir / "squashfs-root"
        if not approot.is_dir():
            return False, "AppImage içeriği çıkarılamadı (squashfs-root)", None

        # Create DEB structure
        deb_root = Path(tmpdir) / "deb"
        deb_root.mkdir()

        # Copy application files to /opt/<app-name>/
        opt_dir = deb_root / "opt" / pkg_name
        if approot.is_dir():
            shutil.copytree(approot, opt_dir, dirs_exist_ok=True)

        # Create DEBIAN/control
        debian_dir = deb_root / "DEBIAN"
        debian_dir.mkdir()

        # Calculate installed size
        total_size = sum(f.stat().st_size for f in opt_dir.rglob("*") if f.is_file())
        installed_size_kb = max(1, total_size // 1024)

        control = (
            f"Package: {pkg_name}\n"
            f"Version: {info.version}\n"
            f"Architecture: amd64\n"
            f"Maintainer: {info.author or 'PkgForge <noreply@pkgforge.app>'}\n"
            f"Description: {info.description or info.name} (converted from AppImage)\n"
            f"Homepage: {info.homepage or 'N/A'}\n"
            f"Installed-Size: {installed_size_kb}\n"
        )
        (debian_dir / "control").write_text(control, encoding="utf-8")

        # Create postinst script to set permissions
        postinst = (
            "#!/bin/bash\n"
            "set -e\n"
            f"chmod +x /opt/{pkg_name}/AppRun 2>/dev/null || true\n"
            f"echo 'Installed {info.name} from AppImage export'\n"
        )
        postinst_path = debian_dir / "postinst"
        postinst_path.write_text(postinst, encoding="utf-8")
        postinst_path.chmod(0o755)

        # Build .deb
        dpkg_deb = shutil.which("dpkg-deb")
        if not dpkg_deb:
            return False, "dpkg-deb bulunamadı — dpkg paketi gerekli", None

        res = safe_run(
            ["dpkg-deb", "--build", str(deb_root), str(output_path)],
            timeout=60,
        )

        if res.returncode != 0:
            return False, tr("appimage.dpkg_deb_basarisiz_res", res_stderr=res.stderr), None

        log.info(tr("appimage.appimage_deb_donusturuldu_s"), output_path)
        return True, tr("appimage.deb_paketi_hazir_output", output_path_name=output_path.name), output_path
