"""PkgForge — Core Constants.

Standardized timeout values and configuration constants.
"""

from __future__ import annotations

from pathlib import Path

# ── Timeout Constants (seconds) ────────────────────────────────
TIMEOUT_FAST = 5        # Quick checks: pacman -Qi, file existence
TIMEOUT_MEDIUM = 30     # Medium ops: tar, ar, rpm2cpio operations
TIMEOUT_SLOW = 120      # Heavy ops: conversions, build operations
TIMEOUT_VERY_SLOW = 600 # Network ops: large downloads, AUR push

# ── Path Constants ──────────────────────────────────────────────
PACMAN_CACHE_DIR = Path("/var/cache/pacman/pkg")
SYSTEMD_DIR = Path("/etc/systemd/system")
AUR_CACHE_DIR = Path.home() / ".cache" / "pkgforge" / "aur"
CONFIG_DIR = Path.home() / ".config" / "pkgforge"
CACHE_DIR = Path.home() / ".cache" / "pkgforge"
PLUGIN_DIR = Path.home() / ".config" / "pkgforge" / "plugins"

# ── Size Limits ─────────────────────────────────────────────────
MAX_PACKAGE_SIZE_MB = 2048
WARN_PACKAGE_SIZE_MB = 500
MAX_PIPE_INPUT_MB = 500
