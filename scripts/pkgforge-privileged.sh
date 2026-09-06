#!/bin/bash
# PkgForge — konsolide yetkili yardimci (F5.4).
# Tum root islemleri icin TEK pkexec giris noktasi. Alt-komutlar kendi
# argumanlarini dogrular; boylece polkit keyfi tee/chmod/rm/systemctl yerine
# yalnizca BU scripti yetkilendirir (atak yuzeyi daralir).
set -euo pipefail

ALLOWED_WRITE_PREFIXES=("/etc/systemd/system/" "/usr/local/bin/" "/usr/share/pkgforge/")

# Test edilebilirlik + farkli dagitim yollari icin ikili konumlari
# ortamdan ezilebilir (uretimde varsayilanlar kullanilir).
SYSTEMCTL_BIN="${PKGForge_SYSTEMCTL:-/usr/bin/systemctl}"
BTRFS_BIN="${PKGForge_BTRFS:-/usr/bin/btrfs}"
ZFS_BIN="${PKGForge_ZFS:-/usr/bin/zfs}"
PACMAN_BIN="${PKGForge_PACMAN:-/usr/bin/pacman}"

usage() {
    echo "Kullanim: pkgforge-privileged.sh <komut> [arg...]" >&2
    echo "  install-pkg [--snapshot AD] <paket>  pacman -U ile kur (tek diyalog)" >&2
    echo "  write-file <yol>         stdin'i dosyaya yaz (atomik)" >&2
    echo "  write-batch <manifest>  manifest'teki dosyaları TEK yetkide yazar" >&2
    echo "  service-deploy <unit>   manifest yaz + daemon-reload + enable + start (TEK diyalog)" >&2
    echo "  service-remove <unit> [dosya...]  stop + disable + sil + daemon-reload (TEK diyalog)" >&2
    echo "  service-enable <unit>   enable + start (TEK diyalog)" >&2
    echo "  service-disable <unit>  stop + disable (TEK diyalog)" >&2
    echo "  snapshot <islem> <hedef>  take-btrfs|delete-btrfs|take-zfs|destroy-zfs" >&2
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

# Ortak dogrulayicilar -------------------------------------------------

_check_unit() {
    local u="$1"
    if [[ "$u" =~ [^A-Za-z0-9._-] ]]; then
        echo "HATA: Gecersiz unit adi: $u" >&2; exit 9
    fi
}

# Manifest okuyup dosyalari yaz (write-batch ile service-deploy ortak kullanir).
_apply_manifest() {
    local n=0
    local MOD DEST CONTENT tmp
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
    echo "$n"
}

# Snapshot adi guvenligi: yalnizca pkgforge- one ekli adlar kabul edilir;
# boylece delete/destroy ile keyfi subvolume/dataset silinemez.
_check_snap_name() {
    local base="$1"
    if [[ "$base" != pkgforge-* ]]; then
        echo "HATA: Snapshot adi pkgforge- ile baslamali: $base" >&2; exit 5
    fi
    if [[ "$base" =~ [^A-Za-z0-9_.@/-] ]]; then
        echo "HATA: Snapshot adinda gecersiz karakter: $base" >&2; exit 5
    fi
}

_take_snapshot() {
    # $1 = istenen ad (pkgforge-...). Varsa btrfs, yoksa zfs dener.
    # Basarida "snapshot-ok: <yol>" basar, basarisizda 1 doner (cagiran
    # kuruluma devam edip etmemeye karar verir).
    local name="$1" base ds
    base="$(basename "$name")"
    _check_snap_name "$base"
    if [ -x "$BTRFS_BIN" ] && "$BTRFS_BIN" filesystem show / >/dev/null 2>&1; then
        if "$BTRFS_BIN" subvolume snapshot / "/$base"; then
            echo "snapshot-ok: /$base"
            return 0
        fi
    fi
    if [ -x "$ZFS_BIN" ]; then
        ds="$("$ZFS_BIN" list -H -o name,mountpoint -t filesystem 2>/dev/null | awk '$2=="/" {print $1}')"
        if [ -n "$ds" ] && "$ZFS_BIN" snapshot -- "$ds@$base"; then
            echo "snapshot-ok: $ds@$base"
            return 0
        fi
    fi
    return 1
}

case "$CMD" in
    install-pkg)
        SNAP=""
        if [ "${1:-}" = "--snapshot" ]; then
            [ $# -ge 3 ] || usage
            SNAP="$2"; shift 2
        fi
        [ $# -eq 1 ] || usage
        PKG_FILE="$1"
        [[ "$PKG_FILE" == /* ]] || { echo "HATA: Mutlak yol gerekli: $PKG_FILE" >&2; exit 2; }
        [ -f "$PKG_FILE" ] || { echo "HATA: Dosya bulunamadi: $PKG_FILE" >&2; exit 3; }
        [[ "$PKG_FILE" == *.pkg.tar* ]] || { echo "HATA: Gecersiz uzanti (yalnizca .pkg.tar.*): $PKG_FILE" >&2; exit 4; }
        if echo "$PKG_FILE" | grep -qE '\.\.'; then echo "HATA: Path traversal: $PKG_FILE" >&2; exit 5; fi
        if [ -n "$SNAP" ]; then
            _take_snapshot "$SNAP" || echo "UYARI: snapshot alinamadi, kuruluma devam ediliyor" >&2
        fi
        exec "$PACMAN_BIN" -U --noconfirm -- "$PKG_FILE"
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
        n="$(_apply_manifest)"
        echo "write-batch: $n dosya yazildi"
        ;;
    service-deploy)
        # Servis kurulumunun TAMAMI tek diyalogda: manifest yaz + reload +
        # enable + start. Ayri ayri 4 pkexec cagrisi = 4 parola diyaloğu
        # demekti; artik 1.
        [ $# -eq 1 ] || usage
        UNIT="$1"; _check_unit "$UNIT"
        n="$(_apply_manifest)"
        "$SYSTEMCTL_BIN" daemon-reload
        "$SYSTEMCTL_BIN" enable -- "$UNIT"
        "$SYSTEMCTL_BIN" start -- "$UNIT"
        echo "service-deploy: $n dosya yazildi, $UNIT etkin"
        ;;
    service-remove)
        # Servis kaldirmanin TAMAMI tek diyalogda: stop + disable + dosya
        # silme + reload. Ayri ayri 6'ya kadar pkexec cagrisi demekti.
        [ $# -ge 1 ] || usage
        UNIT="$1"; shift; _check_unit "$UNIT"
        "$SYSTEMCTL_BIN" stop -- "$UNIT" 2>/dev/null \
            || echo "UYARI: stop basarisiz (servis calismiyor olabilir)" >&2
        "$SYSTEMCTL_BIN" disable -- "$UNIT" 2>/dev/null \
            || echo "UYARI: disable basarisiz" >&2
        for f in "$@"; do
            _check_path "$f"
            _check_not_symlink "$f"
            rm -f -- "$f"
        done
        "$SYSTEMCTL_BIN" daemon-reload
        echo "service-remove: $UNIT kaldirildi"
        ;;
    service-enable)
        # enable + start tek diyalogda.
        [ $# -eq 1 ] || usage
        UNIT="$1"; _check_unit "$UNIT"
        "$SYSTEMCTL_BIN" enable -- "$UNIT"
        "$SYSTEMCTL_BIN" start -- "$UNIT"
        echo "service-enable: $UNIT etkin"
        ;;
    service-disable)
        # stop + disable tek diyalogda.
        [ $# -eq 1 ] || usage
        UNIT="$1"; _check_unit "$UNIT"
        "$SYSTEMCTL_BIN" stop -- "$UNIT" 2>/dev/null \
            || echo "UYARI: stop basarisiz" >&2
        "$SYSTEMCTL_BIN" disable -- "$UNIT" 2>/dev/null \
            || echo "UYARI: disable basarisiz" >&2
        echo "service-disable: $UNIT devre disi"
        ;;
    snapshot)
        # Dosya-sistemi snapshot islemleri tek diyalogda. Hedef adlar
        # pkgforge- one ekiyle sinirli — keyfi subvolume/dataset
        # silinemez/olusturulamaz.
        [ $# -eq 2 ] || usage
        OP="$1"; TARGET="$2"
        [[ "$TARGET" == /* ]] || { echo "HATA: Mutlak yol gerekli: $TARGET" >&2; exit 2; }
        if echo "$TARGET" | grep -qE '\.\.'; then echo "HATA: Path traversal: $TARGET" >&2; exit 5; fi
        case "$OP" in
            take-btrfs)
                [[ "$TARGET" =~ ^/[^/]+$ ]] || { echo "HATA: btrfs hedefi kok dizinde tek duzey olmali: $TARGET" >&2; exit 5; }
                _check_snap_name "$(basename "$TARGET")"
                [ -x "$BTRFS_BIN" ] || { echo "HATA: btrfs bulunamadi" >&2; exit 3; }
                "$BTRFS_BIN" subvolume snapshot / -- "$TARGET"
                echo "snapshot-ok: $TARGET"
                ;;
            delete-btrfs)
                _check_snap_name "$(basename "$TARGET")"
                [ -x "$BTRFS_BIN" ] || { echo "HATA: btrfs bulunamadi" >&2; exit 3; }
                "$BTRFS_BIN" subvolume delete -- "$TARGET"
                echo "snapshot-silindi: $TARGET"
                ;;
            take-zfs|destroy-zfs)
                [[ "$TARGET" == *@* ]] || { echo "HATA: ZFS hedefi dataset@snap biciminde olmali: $TARGET" >&2; exit 5; }
                _check_snap_name "${TARGET#*@}"
                if [[ "${TARGET%@*}" =~ [^A-Za-z0-9._/-] ]]; then echo "HATA: Gecersiz dataset: $TARGET" >&2; exit 5; fi
                [ -x "$ZFS_BIN" ] || { echo "HATA: zfs bulunamadi" >&2; exit 3; }
                if [ "$OP" = "take-zfs" ]; then
                    "$ZFS_BIN" snapshot -- "$TARGET"
                else
                    "$ZFS_BIN" destroy -- "$TARGET"
                fi
                echo "snapshot-ok: $TARGET"
                ;;
            *)
                echo "HATA: Gecersiz snapshot islemi: $OP" >&2; exit 8
                ;;
        esac
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
                exec "$SYSTEMCTL_BIN" daemon-reload
                ;;
            enable|disable|start|stop)
                [ $# -eq 2 ] || usage
                UNIT="$2"
                _check_unit "$UNIT"
                exec "$SYSTEMCTL_BIN" "$VERB" -- "$UNIT"
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
