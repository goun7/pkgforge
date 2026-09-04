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
    echo "  write-batch <manifest>  manifest'teki dosyaları TEK yetkide yazar" >&2
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
    # SEC: symlink'li bilesenleri cozmeden yapilan string-prefix karsilastirmasi
    # atlanabilir; once kanonik yolu coz, prefix'i O yola uygula.
    local real
    real="$(realpath -m "$p")"
    local ok=false
    for prefix in "${ALLOWED_WRITE_PREFIXES[@]}"; do
        if [[ "$real" == "$prefix"* ]]; then ok=true; break; fi
    done
    if [ "$ok" = false ]; then
        echo "HATA: Yol izin verilen dizinlerde degil: $p" >&2; exit 6
    fi
}

# Izinli bir prefix'in icine yerlestirilmis bir sembolik bag, hedefi disari
# tasirabilir (orn. /usr/share/pkgforge/x -> /etc/shadow). chmod symlink'i
# takip eder; write-file'in ebeveyn dizini bir symlink ise kacis olur. Bu
# nedenle hedefin ve (write-file icin) ebeveyninin symlink olmamasi sart.
_check_not_symlink() {
    local p="$1"
    if [ -L "$p" ]; then
        echo "HATA: Sembolik bag hedefi reddedildi: $p" >&2; exit 10
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
        # SEC: mkdir sonrasi yeniden coz (symlink'li ust dizin kacisini kapat)
        # ve mktemp (O_EXCL) ile tahmin edilebilir tmp yarisi engellenir.
        DEST="$(realpath -m "$DEST")"
        _check_path "$DEST"
        _check_not_symlink "$DEST"
        mkdir -p "$(dirname "$DEST")"
        _check_not_symlink "$(dirname "$DEST")"
        tmp="$(mktemp "$DEST.XXXXXX")"
        cat > "$tmp"
        mv -f "$tmp" "$DEST"
        ;;
    write-batch)
        # Faz 14: coklu dosya yazmayi TEK pkexec diyalogunda topla.
        # Manifest stdin'den gelir; her satir: "<mod>:<yol>:" sonra icerik,
        # NUL ayiriciyla (icerikte newline guvenli; bos satir dahi yazilir).
        [ $# -eq 0 ] || usage
        n=0
        while IFS= read -r -d '' header; do
            MOD="$header"
            IFS= read -r -d '' DEST || { echo "HATA: Eksik hedef yolu" >&2; exit 11; }
            IFS= read -r -d '' CONTENT || true
            _check_path "$DEST"
            DEST="$(realpath -m "$DEST")"
            _check_path "$DEST"
            _check_not_symlink "$DEST"
            mkdir -p "$(dirname "$DEST")"
            _check_not_symlink "$(dirname "$DEST")"
            tmp="$(mktemp "$DEST.XXXXXX")"
            printf '%s' "$CONTENT" > "$tmp"
            chmod "$MOD" "$tmp" 2>/dev/null || true
            mv -f "$tmp" "$DEST"
            n=$((n+1))
        done
        echo "write-batch: $n dosya yazildi"
        ;;
    chmod)
        [ $# -eq 2 ] || usage
        MODE="$1"; DEST="$2"
        [[ "$MODE" =~ ^[0-7]{3,4}$ ]] || { echo "HATA: Gecersiz mod: $MODE" >&2; exit 7; }
        _check_path "$DEST"
        _check_not_symlink "$DEST"
        chmod "$MODE" "$DEST"
        ;;
    remove-file)
        [ $# -eq 1 ] || usage
        DEST="$1"
        _check_path "$DEST"
        _check_not_symlink "$DEST"
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
