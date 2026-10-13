"""Path containment for the RPC/HTTP surface.

Why this exists: the desktop sidecar accepts file-path parameters, and before
this module it only checked `is_file()`. Probes showed `security.verify`
accepting `/etc/shadow`, `system.open_path` actually running `xdg-open /etc`,
`queue.add` persisting `/etc/passwd`, and `install.rehearse` bind-mounting host
`/etc` into a container. A tool that installs packages as root must not let its
local socket turn a path parameter into arbitrary host access.

Policy: user data locations are allowed (home, our cache/temp dirs, the pacman
cache); OS and credential locations are denied even for the owning user. A
symlink is resolved before the check so an allowed link cannot point into a
denied tree.
"""

from __future__ import annotations

import os
from pathlib import Path

# Denied absolute roots: system state, boot, kernel interfaces, and other
# users' homes. Denied regardless of who asks.
DENIED_ROOTS: tuple[str, ...] = (
    "/bin", "/boot", "/dev", "/etc", "/lib", "/lib32", "/lib64", "/proc",
    "/root", "/run", "/sbin", "/sys", "/usr", "/var",
)

#: `/var` is denied wholesale, but these sub-paths are legitimate package work
#: locations on Arch and must keep working. (B108 is a false positive here:
#: these are policy string constants, not temp file/directory usage.)
ALLOWED_UNDER_DENY: tuple[str, ...] = (  # nosec B108
    "/var/cache/pacman",
    "/var/tmp",
)

#: Sensitive credential directories inside the caller's own home.
DENIED_HOME_SUBPATHS: tuple[str, ...] = (
    ".ssh", ".gnupg", ".password-store", ".aws", ".config/gcloud",
)

__all__ = [
    "ALLOWED_UNDER_DENY",
    "DENIED_HOME_SUBPATHS",
    "DENIED_ROOTS",
    "PathNotAllowed",
    "guarded_path",
    "guarded_paths",
]


class PathNotAllowed(ValueError):
    """Raised when a request path is outside the containment policy."""


def _normalize(path: str | Path) -> Path:
    raw = Path(str(path).strip()).expanduser()
    try:
        # strict=False: the target may not exist yet (output paths, backups).
        return Path(os.path.realpath(raw, strict=False))
    except (OSError, RuntimeError):
        # Unresolvable (broken symlink loop): fall back to lexical normalization
        # so containment is still evaluated instead of silently allowed.
        return Path(os.path.normpath(str(raw)))


def _under(child: Path, parent: str) -> bool:
    text = str(child)
    return text == parent or text.startswith(parent.rstrip("/") + "/")


def _denied_home_subpaths() -> list[str]:
    home = Path(os.path.expanduser("~"))
    return [str(home / sub) for sub in DENIED_HOME_SUBPATHS]


def guarded_path(value: str | Path, *, field: str = "path") -> Path:
    """Return the resolved path or raise PathNotAllowed.

    Blank input is rejected: callers previously accepted
    `params.get('pkg_path', '')` and only failed later with a confusing
    "Package not found". Callers that treat "" as "use my default destination"
    must check for blank themselves before calling this.
    """
    text = str(value or "").strip()
    if not text:
        raise PathNotAllowed(f"{field}: bos yol kabul edilmez")

    resolved = _normalize(text)

    for denied in _denied_home_subpaths():
        if _under(resolved, denied):
            raise PathNotAllowed(f"{field}: kimlik/kredi dizini reddedildi")

    for denied in DENIED_ROOTS:
        if _under(resolved, denied):
            if any(_under(resolved, ok) for ok in ALLOWED_UNDER_DENY):
                break
            raise PathNotAllowed(f"{field}: sistem yolu reddedildi ({denied})")

    return resolved


def guarded_paths(values: list[str] | tuple[str, ...] | None,
                  *, field: str = "paths") -> list[Path]:
    """Guard every entry of a path list; rejects an empty list."""
    items = list(values or [])
    if not items:
        raise PathNotAllowed(f"{field}: liste bos olamaz")
    return [guarded_path(v, field=f"{field}[{i}]") for i, v in enumerate(items)]
