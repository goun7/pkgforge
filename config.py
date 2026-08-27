"""PkgForge — Configuration & Constants."""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "PkgForge"
APP_VERSION = "2.0.0"
APP_ID = "org.pkgforge.app"

# Destek/bağış (FUNDING.yml ile aynı hedefleri işaret eder; GitHub Sponsors
# etkinleşene kadar Polar/Kreosus yansıtıcıları kullanılır).
REPO_URL = "https://github.com/goun7/pkgforge"
DONATE_URL = "https://polar.sh/goun7"

# Settings
CONFIG_DIR = Path.home() / ".config" / "pkgforge"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# ── Profiles (C2) ────────────────────────────────────────────────
# The base dir stays CONFIG_DIR; the active profile rebinds where
# settings.json / history.db live. "default" maps to CONFIG_DIR itself so
# existing installs keep their data without migration. All access goes through
# these functions (never capture CONFIG_DIR bindings elsewhere) so tests can
# monkeypatch config.CONFIG_DIR and every resolver follows.
DEFAULT_PROFILE = "default"
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def profiles_dir() -> Path:
    """Root directory holding non-default profiles."""
    return CONFIG_DIR / "profiles"


def active_profile_file() -> Path:
    """Marker file storing the active profile name."""
    return CONFIG_DIR / "active_profile"


def get_active_profile() -> str:
    """Return the active profile name ('default' when unset/corrupt)."""
    try:
        name = active_profile_file().read_text(encoding="utf-8").strip()
    except OSError:
        return DEFAULT_PROFILE
    return name if name and PROFILE_NAME_RE.match(name) else DEFAULT_PROFILE


def profile_config_dir(profile: str | None = None) -> Path:
    """Config dir for a profile: CONFIG_DIR for 'default', profiles/<n> otherwise."""
    name = profile or get_active_profile()
    if name == DEFAULT_PROFILE:
        return CONFIG_DIR
    return profiles_dir() / name


def settings_file(profile: str | None = None) -> Path:
    """Active-profile-aware path to settings.json."""
    return profile_config_dir(profile) / "settings.json"


def history_db_path(profile: str | None = None) -> Path:
    """Active-profile-aware path to history.db."""
    return profile_config_dir(profile) / "history.db"


def backup_dir(profile: str | None = None) -> Path:
    """Active-profile-aware path to the package backups directory."""
    return profile_config_dir(profile) / "backups"


def queue_db_path(profile: str | None = None) -> Path:
    """Active-profile-aware path to the batch-queue persistence db (F5.12)."""
    return profile_config_dir(profile) / "queue.db"

# Offline mode — when True, network-dependent checks (AUR, upstream) are skipped
OFFLINE_MODE: bool = False

# Size limits (re-export from core.constants for backward compatibility).
# These are imported by core.pipeline and others via "from config import ...",
# so they must stay even though config.py does not use them directly.
from core.constants import MAX_PACKAGE_SIZE_MB, WARN_PACKAGE_SIZE_MB  # noqa: F401

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

# AUR RPC endpoints
AUR_RPC_URL = "https://aur.archlinux.org/rpc/v5/info"
AUR_SEARCH_URL = "https://aur.archlinux.org/rpc/v5/search"


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
        # Supports Unicode package names (CJK, Cyrillic, etc.)
        stem = name.rsplit(".", 1)[0]  # strip .rpm
        # Strip epoch prefix (e.g., "1:" in "1:openssl-1.1.1k-4")
        if ":" in stem:
            stem = stem.split(":", 1)[1]
        # Remove arch suffix — dot or hyphen separated
        # Unicode-safe: supports x86_64, noarch, aarch64, etc.
        stem = _re.sub(r"[.\-](x86_64|noarch|i686|i386|aarch64|armv7hl|s390x|ppc64le)$", "", stem)
        # Split by hyphens; last two segments are version-release
        parts = stem.split("-")
        if len(parts) >= 3:
            return "-".join(parts[:-2])
        elif len(parts) == 2:
            return parts[0]
        return stem

    elif lower.endswith((".pkg.tar.zst", ".pkg.tar.xz")):
        # Arch: name-version-release-arch.pkg.tar.*
        stem = name.rsplit(".", 1)[0]  # strip .zst or .xz
        stem = stem.rsplit(".", 1)[0]  # strip .tar
        parts = stem.split("-")
        if len(parts) >= 4:
            return "-".join(parts[:-3])
        return stem

    # Unknown format: return stem as-is
    return Path(filename).stem

