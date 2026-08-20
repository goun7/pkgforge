"""PkgForge — Configuration & Constants."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_NAME = "PkgForge"
APP_VERSION = "1.1.0"
APP_ID = "org.pkgforge.app"

# Settings
CONFIG_DIR = Path.home() / ".config" / "pkgforge"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# Offline mode — when True, network-dependent checks (AUR, upstream) are skipped
OFFLINE_MODE: bool = False

# Size limits
MAX_PACKAGE_SIZE_MB = 2048
WARN_PACKAGE_SIZE_MB = 500

# Supported architectures (Arch naming)
SUPPORTED_ARCHES = frozenset({"x86_64", "any"})

# DEB arch → Arch arch mapping
DEB_ARCH_MAP: dict[str, str] = {
    "amd64": "x86_64",
    "all": "any",
    "i386": "i686",
    "arm64": "aarch64",
    "armhf": "armv7h",
}

# RPM arch → Arch arch mapping
RPM_ARCH_MAP: dict[str, str] = {
    "x86_64": "x86_64",
    "noarch": "any",
    "i686": "i686",
    "i386": "i686",
    "aarch64": "aarch64",
}

# Known RPM → Arch dependency name mapping
RPM_DEP_MAP: dict[str, str] = {
    "glibc": "glibc",
    "libX11": "libx11",
    "libXext": "libxext",
    "libXrender": "libxrender",
    "libxcb": "libxcb",
    "libGL": "mesa",
    "libEGL": "mesa",
    "alsa-lib": "alsa-lib",
    "libpulse": "libpulse",
    "libdbus-1": "dbus",
    "libgio-2.0": "glib2",
    "libglib-2.0": "glib2",
    "libgobject-2.0": "glib2",
    "libgtk-3": "gtk3",
    "libgtk-4": "gtk4",
    "libcairo": "cairo",
    "libpango-1.0": "pango",
    "libatk-1.0": "at-spi2-core",
    "libcurl": "curl",
    "libssl": "openssl",
    "libcrypto": "openssl",
    "zlib": "zlib",
    "libnss3": "nss",
    "libnspr4": "nspr",
    "libsqlite3": "sqlite",
    "libfontconfig": "fontconfig",
    "libfreetype": "freetype2",
}

# AUR RPC endpoint
AUR_RPC_URL = "https://aur.archlinux.org/rpc/v5/info"


@dataclass(frozen=True)
class ToolPaths:
    """Discovered paths to required external tools."""

    debtap: str = ""
    rpm2cpio: str = ""
    makepkg: str = ""
    namcap: str = ""
    pacman: str = ""
    pkexec: str = ""
    fakeroot: str = ""
    bwrap: str = ""
    file_cmd: str = ""
    gpg: str = ""
    ldd: str = ""
    ar: str = ""
    bsdtar: str = ""
    distrobox: str = ""
    paru: str = ""
    yay: str = ""
    readelf: str = ""
    objdump: str = ""

    @property
    def missing_required(self) -> list[str]:
        required = {
            "pacman": self.pacman,
            "makepkg": self.makepkg,
            "fakeroot": self.fakeroot,
            "file": self.file_cmd,
            "pkexec": self.pkexec,
            "bsdtar": self.bsdtar,
        }
        return [name for name, path in required.items() if not path]

    @property
    def missing_optional(self) -> list[str]:
        optional = {
            "debtap": self.debtap,
            "rpm2cpio": self.rpm2cpio,
            "namcap": self.namcap,
            "bwrap": self.bwrap,
            "gpg": self.gpg,
            "ldd": self.ldd,
            "ar": self.ar,
        }
        return [name for name, path in optional.items() if not path]

    @property
    def has_distrobox(self) -> bool:
        return bool(self.distrobox)


def discover_tools() -> ToolPaths:
    """Discover all external tool paths using shutil.which()."""

    def _find(name: str) -> str:
        return shutil.which(name) or ""

    return ToolPaths(
        debtap=_find("debtap"),
        rpm2cpio=_find("rpm2cpio"),
        makepkg=_find("makepkg"),
        namcap=_find("namcap"),
        pacman=_find("pacman"),
        pkexec=_find("pkexec"),
        fakeroot=_find("fakeroot"),
        bwrap=_find("bwrap"),
        file_cmd=_find("file"),
        gpg=_find("gpg"),
        ldd=_find("ldd"),
        ar=_find("ar"),
        bsdtar=_find("bsdtar"),
        distrobox=_find("distrobox"),
        paru=_find("paru"),
        yay=_find("yay"),
        readelf=_find("readelf"),
        objdump=_find("objdump"),
    )


def create_temp_dir() -> Path:
    """Create a secure temporary directory with 700 permissions."""
    path = Path(tempfile.mkdtemp(prefix="pkgforge_"))
    path.chmod(0o700)
    return path


def cleanup_orphaned_temp_dirs() -> int:
    """Scan temp directory for orphaned pkgforge_* folders and remove them."""
    temp_root = Path(tempfile.gettempdir())
    removed_count = 0
    for item in temp_root.glob("pkgforge_*"):
        if item.is_dir():
            try:
                shutil.rmtree(item)
                removed_count += 1
            except OSError:
                pass
    return removed_count


# ── Smart Package Name Extraction ────────────────────────────────

def extract_package_name(filename: str) -> str:
    """Extract a clean package name from a .deb or .rpm filename.

    Handles Debian naming conventions:
      name_version_arch.deb  → name
      libssl1.1_1.1.0-1_amd64.deb → libssl1.1
      python3-pip_21.0-1_all.deb → python3-pip

    RPM naming:
      name-version-release.arch.rpm → name
      openssl-1.1.1k-4-x86_64.rpm → openssl
      glibc-2.33-5.fc34.x86_64.rpm → glibc

    URL paths are basename-extracted first.
    """
    import re as _re

    # Extract basename from URL or path
    name = Path(filename).name
    if not name:
        return filename

    # Determine if deb or rpm
    lower = name.lower()
    if lower.endswith(".deb"):
        # Debian: name_version_arch.deb
        stem = name.rsplit(".", 1)[0]  # strip .deb
        parts = stem.split("_")
        if len(parts) >= 2:
            # First part is the package name (may contain dots, e.g. libssl1.1)
            return parts[0]
        # Fallback: strip trailing -version
        return _re.sub(r"-[\d].*$", "", stem)

    elif lower.endswith(".rpm"):
        # RPM: [epoch:]name-version-release.arch.rpm
        stem = name.rsplit(".", 1)[0]  # strip .rpm
        # Strip epoch prefix (e.g., "1:" in "1:openssl-1.1.1k-4")
        if ":" in stem:
            stem = stem.split(":", 1)[1]
        # Remove arch suffix — dot or hyphen separated
        # (e.g., ".x86_64" in "openssl-4.x86_64" or "-x86_64" in "openssl-4-x86_64")
        stem = _re.sub(r"[.\-](x86_64|noarch|i686|i386|aarch64|armv7hl)$", "", stem)
        # Split by hyphens; last two segments are version-release
        parts = stem.split("-")
        if len(parts) >= 3:
            return "-".join(parts[:-2])
        elif len(parts) == 2:
            return parts[0]
        return stem

    elif lower.endswith(".pkg.tar.zst") or lower.endswith(".pkg.tar.xz"):
        # Arch: name-version-release-arch.pkg.tar.*
        stem = name.rsplit(".", 1)[0]  # strip .zst or .xz
        stem = stem.rsplit(".", 1)[0]  # strip .tar
        parts = stem.split("-")
        if len(parts) >= 4:
            return "-".join(parts[:-3])
        return stem

    # Unknown format: return stem as-is
    return Path(filename).stem

