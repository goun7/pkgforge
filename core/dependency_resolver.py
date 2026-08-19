"""PkgForge — Runtime dependency resolver.

.. deprecated::
    Use ``core.dep_resolver`` instead. This module re-exports everything
    for backward compatibility.
"""

from core.dep_resolver import (
    parse_needed_sonames,
    parse_objdump_sonames,
    is_elf_file,
    collect_sonames,
    sonames_to_packages,
    resolve_runtime_dependencies,
)

__all__ = [
    "parse_needed_sonames",
    "parse_objdump_sonames",
    "is_elf_file",
    "collect_sonames",
    "sonames_to_packages",
    "resolve_runtime_dependencies",
]
