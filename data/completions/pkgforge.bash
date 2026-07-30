# PkgForge Bash Completion

_pkgforge_completions() {
    local cur prev subcmds
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    subcmds="convert list remove rollback check-updates gui"

    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "$subcmds --help --version --check-deps --install-deps" -- "$cur") )
        return 0
    fi

    case "$prev" in
        convert)
            COMPREPLY=( $(compgen -f -X '!*@(.deb|.rpm)' -- "$cur") )
            return 0
            ;;
        remove|rollback)
            COMPREPLY=( $(compgen -W "$(pacman -Qq 2>/dev/null)" -- "$cur") )
            return 0
            ;;
    esac
}

complete -F _pkgforge_completions pkgforge
