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

