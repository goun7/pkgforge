"""PkgForge — Shell Completion Generator.

Generates completion scripts for bash, zsh, and fish shells.

Usage:
    from core.completion import generate_completion
    script = generate_completion("bash")
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

COMMANDS = [
    "convert", "list", "remove", "rollback", "check-updates", "delta",
    "flatpak-export", "appimage-export", "graph", "audit", "scan-image",
    "abi-check", "health", "snapshot-cleanup", "quality", "publish",
    "verify-rollback", "from-source", "rpm-to-deb", "provenance",
    "benchmark", "sign", "verify", "sbom", "attest", "plugin", "gui",
]

CONVERT_FLAGS = [
    "--install", "-i", "--yes", "-y", "--dry-run", "--output-dir", "-o",
    "--to-oci", "--oci-tag", "--delta", "--verify-build", "--sign",
    "--sign-key", "--resolve-deps",
]

GLOBAL_FLAGS = [
    "--file", "-f", "--lang", "-l", "--theme", "-t", "--version", "-v",
    "--check-deps", "--install-deps", "--offline", "--clear-cache",
    "--help", "-h",
]

PLUGIN_SUBCOMMANDS = ["install", "list", "available", "remove", "update", "audit"]
DELTA_SUBCOMMANDS = ["status", "enable", "disable"]


def generate_completion(shell: str) -> str:
    """Generate a shell completion script.

    Args:
        shell: Shell type ("bash", "zsh", or "fish").

    Returns:
        Completion script as string.
    """
    if shell == "bash":
        return _bash_completion()
    elif shell == "zsh":
        return _zsh_completion()
    elif shell == "fish":
        return _fish_completion()
    else:
        raise ValueError(f"Unsupported shell: {shell}. Use bash, zsh, or fish.")


def _bash_completion() -> str:
    """Generate bash completion script."""
    cmds = " ".join(COMMANDS)
    flags = " ".join(GLOBAL_FLAGS)
    return f'''# PkgForge bash completion
_pkgforge() {{
    local cur prev commands flags
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    commands="{cmds}"
    flags="{flags}"

    if [[ ${{COMP_CWORD}} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands $flags" -- "$cur") )
        return 0
    fi

    case "${{COMP_WORDS[1]}}" in
        convert)
            COMPREPLY=( $(compgen -W "{(' '.join(CONVERT_FLAGS))} -" -- "$cur") )
            ;;
        plugin)
            COMPREPLY=( $(compgen -W "{' '.join(PLUGIN_SUBCOMMANDS)}" -- "$cur") )
            ;;
        delta)
            COMPREPLY=( $(compgen -W "{' '.join(DELTA_SUBCOMMANDS)}" -- "$cur") )
            ;;
    esac
    return 0
}}
complete -F _pkgforge pkgforge
'''


def _zsh_completion() -> str:
    """Generate zsh completion script."""
    cmds = " ".join(f'"{c}"' for c in COMMANDS)
    return f'''#compdef pkgforge

_pkgforge() {{
    local -a commands
    commands=({cmds})

    _arguments -C \\
        '1:command:->command' \\
        '*::arg:->args'

    case $state in
        command)
            _describe 'command' commands
            ;;
        args)
            case $words[1] in
                convert)
                    _arguments \\
                        '--install[Auto-install after conversion]' \\
                        '--yes[Skip confirmation]' \\
                        '--dry-run[Analyze without converting]' \\
                        '-o[Output directory]:directory:_directories' \\
                        '--to-oci[Export as OCI container]' \\
                        '--delta[Use binary delta download]' \\
                        '--sign[Sign package with GPG]'
                    ;;
                plugin)
                    _values 'action' install list available remove update audit
                    ;;
                delta)
                    _values 'action' status enable disable
                    ;;
            esac
            ;;
    esac
}}
_pkgforge "$@"
'''


def _fish_completion() -> str:
    """Generate fish completion script."""
    cmds = "\n".join(f"complete -c pkgforge -f -n '__fish_use_subcommand' -a '{c}'" for c in COMMANDS)
    return f'''# PkgForge fish completion
{cmds}

complete -c pkgforge -l help -s h -d 'Show help'
complete -c pkgforge -l version -s v -d 'Show version'
complete -c pkgforge -l lang -s l -d 'Language (tr/en)'
complete -c pkgforge -l theme -s t -d 'Theme (dark/light/system)'
complete -c pkgforge -l offline -d 'Run in offline mode'
complete -c pkgforge -l file -s f -d 'Package file path'

# Convert subcommand
complete -c pkgforge -n '__fish_seen_subcommand_from convert' -l install -s i -d 'Auto-install'
complete -c pkgforge -n '__fish_seen_subcommand_from convert' -l yes -s y -d 'Skip confirmation'
complete -c pkgforge -n '__fish_seen_subcommand_from convert' -l dry-run -d 'Dry run'
complete -c pkgforge -n '__fish_seen_subcommand_from convert' -l output-dir -s o -d 'Output directory'
complete -c pkgforge -n '__fish_seen_subcommand_from convert' -l to-oci -d 'Export as OCI'
complete -c pkgforge -n '__fish_seen_subcommand_from convert' -l sign -d 'Sign with GPG'

# Plugin subcommands
complete -c pkgforge -n '__fish_seen_subcommand_from plugin' -a install -d 'Install plugin'
complete -c pkgforge -n '__fish_seen_subcommand_from plugin' -a list -d 'List plugins'
complete -c pkgforge -n '__fish_seen_subcommand_from plugin' -a available -d 'Available plugins'
complete -c pkgforge -n '__fish_seen_subcommand_from plugin' -a remove -d 'Remove plugin'
complete -c pkgforge -n '__fish_seen_subcommand_from plugin' -a update -d 'Update plugin'
complete -c pkgforge -n '__fish_seen_subcommand_from plugin' -a audit -d 'Audit plugins'

# Delta subcommands
complete -c pkgforge -n '__fish_seen_subcommand_from delta' -a status -d 'Show status'
complete -c pkgforge -n '__fish_seen_subcommand_from delta' -a enable -d 'Enable auto-update'
complete -c pkgforge -n '__fish_seen_subcommand_from delta' -a disable -d 'Disable auto-update'
'''
