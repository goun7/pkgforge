"""tomllib compatibility shim (PEP 680).

Python 3.11+ ships tomllib; 3.10 needs the tomli backport. Everything in
the codebase imports the parser from here so the declared floor
(requires-python >=3.10) stays honest.
"""

from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    import tomllib as _mod
else:  # pragma: no cover - exercised only on 3.10
    try:
        import tomli as _mod
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Python 3.10 requires the 'tomli' package for TOML parsing. "
            "Install it with: pip install tomli"
        ) from exc

TOMLDecodeError = _mod.TOMLDecodeError
load = _mod.load
loads = _mod.loads

__all__ = ["TOMLDecodeError", "load", "loads"]
