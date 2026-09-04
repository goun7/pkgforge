"""Safe single-quoted bash literals for generated PKGBUILD files.

PKGBUILD files are sourced by makepkg with bash: any unescaped
command-substitution vector in metadata (description, url, ...) becomes
arbitrary code execution in the user session. All untrusted strings must
pass through pkgbuild_literal() before embedding.
"""

from __future__ import annotations

import re

# Backtick and $( are command-substitution vectors even outside quotes in
# eval-like contexts; strip them instead of trying to outsmart bash quoting.
_VECTOR_RE = re.compile("[`\\\\]|[$][(]")


def sanitize_bash_literal(value: str) -> str:
    """Remove command-substitution vectors before quoting."""
    return _VECTOR_RE.sub("", value)


def bash_single_quote(value: str) -> str:
    """Single-quote a string for bash (it + escaped quote + s)."""
    return "'" + value.replace("'", "'\\''") + "'"


def pkgbuild_literal(value: str | None) -> str:
    """Quote an untrusted string for direct embedding in a PKGBUILD."""
    return bash_single_quote(sanitize_bash_literal(str(value or "")))
