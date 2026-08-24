#!/bin/bash
# PkgForge — konsolide yetkili yardimci (F5.4).
# Tum root islemleri icin TEK pkexec giris noktasi. Alt-komutlar kendi
# argumanlarini dogrular; boylece polkit keyfi tee/chmod/rm/systemctl yerine
# yalnizca BU scripti yetkilendirir (atak yuzeyi daralir).
set -euo pipefail

ALLOWED_WRITE_PREFIXES=("/etc/systemd/system/" "/usr/local/bin/" "/usr/share/pkgforge/")

usage() {
    echo "Kullanim: pkgforge-privileged.sh <komut> [arg...]" >&2
    echo "  install-pkg <paket>      pacman -U ile kur" >&2
    echo "  write-file <yol>         stdin'i dosyaya yaz (atomik)" >&2
    echo "  chmod <mod> <yol>        dosya modunu degistir" >&2
    echo "  remove-file <yol>        dosyayi sil" >&2
    echo "  systemctl <fiil> [unit]  enable|disable|start|stop|daemon-reload" >&2
    exit 1
}

_check_path() {
    local p="$1"
    if [[ "$p" != /* ]]; then
        echo "HATA: Mutlak yol gerekli: $p" >&2; exit 2
    fi
    if echo "$p" | grep -qE '\.\.'; then
        echo "HATA: Path traversal tespit edildi: $p" >&2; exit 5
    fi
    local ok=false
    for prefix in "${ALLOWED_WRITE_PREFIXES[@]}"; do
        if [[ "$p" == "$prefix"* ]]; then ok=true; break; fi
    done
    if [ "$ok" = false ]; then
        echo "HATA: Yol izin verilen dizinlerde degil: $p" >&2; exit 6
    fi
}

[ $# -ge 1 ] || usage
CMD="$1"; shift

case "$CMD" in
    install-pkg)
        [ $# -eq 1 ] || usage
        PKG_FILE="$1"
        [[ "$PKG_FILE" == /* ]] || { echo "HATA: Mutlak yol gerekli: $PKG_FILE" >&2; exit 2; }
        [ -f "$PKG_FILE" ] || { echo "HATA: Dosya bulunamadi: $PKG_FILE" >&2; exit 3; }
        [[ "$PKG_FILE" == *.pkg.tar* ]] || { echo "HATA: Gecersiz uzanti (yalnizca .pkg.tar.*): $PKG_FILE" >&2; exit 4; }
        if echo "$PKG_FILE" | grep -qE '\.\.'; then echo "HATA: Path traversal: $PKG_FILE" >&2; exit 5; fi
        exec /usr/bin/pacman -U --noconfirm -- "$PKG_FILE"
        ;;
    write-file)
        [ $# -eq 1 ] || usage
        DEST="$1"
        _check_path "$DEST"
        mkdir -p "$(dirname "$DEST")"
        tmp="$DEST.tmp"
        cat > "$tmp"
        mv "$tmp" "$DEST"
        ;;
    chmod)
        [ $# -eq 2 ] || usage
        MODE="$1"; DEST="$2"
        [[ "$MODE" =~ ^[0-7]{3,4}$ ]] || { echo "HATA: Gecersiz mod: $MODE" >&2; exit 7; }
        _check_path "$DEST"
        chmod "$MODE" "$DEST"
        ;;
    remove-file)
        [ $# -eq 1 ] || usage
        DEST="$1"
        _check_path "$DEST"
        rm -f -- "$DEST"
        ;;
    systemctl)
        [ $# -ge 1 ] || usage
        VERB="$1"
        case "$VERB" in
            daemon-reload)
                exec /usr/bin/systemctl daemon-reload
                ;;
            enable|disable|start|stop)
                [ $# -eq 2 ] || usage
                UNIT="$2"
                if [[ "$UNIT" =~ [^A-Za-z0-9._-] ]]; then
                    echo "HATA: Gecersiz unit adi: $UNIT" >&2; exit 9
                fi
                exec /usr/bin/systemctl "$VERB" -- "$UNIT"
                ;;
            *)
                echo "HATA: Gecersiz systemctl fiili: $VERB" >&2; exit 8
                ;;
        esac
        ;;
    *)
        usage
        ;;
esac
