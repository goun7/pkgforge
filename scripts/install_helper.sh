#!/bin/bash
# PkgForge — Install helper script
# Called via pkexec for privilege escalation.
# Validates arguments and executes pacman -U safely.

set -euo pipefail

# ── Argument validation ──────────────────────────────────────────

if [ $# -ne 1 ]; then
    echo "Kullanım: install_helper.sh <paket_dosyası>" >&2
    exit 1
fi

PKG_FILE="$1"

# Must be an absolute path
if [[ "$PKG_FILE" != /* ]]; then
    echo "HATA: Mutlak yol gerekli: $PKG_FILE" >&2
    exit 2
fi

# Must exist
if [ ! -f "$PKG_FILE" ]; then
    echo "HATA: Dosya bulunamadı: $PKG_FILE" >&2
    exit 3
fi

# Must have .pkg.tar extension
if [[ "$PKG_FILE" != *.pkg.tar* ]]; then
    echo "HATA: Geçersiz dosya uzantısı (yalnızca .pkg.tar.* kabul edilir): $PKG_FILE" >&2
    exit 4
fi

# Must not contain path traversal
if echo "$PKG_FILE" | grep -qE '\.\.'; then
    echo "HATA: Path traversal tespit edildi: $PKG_FILE" >&2
    exit 5
fi

# Must be in a temp directory or user's home (not system dirs).
# TMPDIR is honored so custom temp locations (e.g. /run/user/1000) work too.
ALLOWED_PREFIXES=("/tmp" "/home" "/var/tmp")
if [ -n "${TMPDIR:-}" ]; then
    ALLOWED_PREFIXES+=("${TMPDIR%/}")
fi
VALID=false
for prefix in "${ALLOWED_PREFIXES[@]}"; do
    if [[ "$PKG_FILE" == "$prefix"* ]]; then
        VALID=true
        break
    fi
done

if [ "$VALID" = false ]; then
    echo "HATA: Paket dosyası izin verilen dizinlerde değil: $PKG_FILE" >&2
    echo "İzin verilen: ${ALLOWED_PREFIXES[*]}" >&2
    exit 6
fi

# ── Execute installation ─────────────────────────────────────────

echo "Paket kuruluyor: $(basename "$PKG_FILE")"
# '--' guards against a package path starting with '-' being parsed as an option
exec /usr/bin/pacman -U --noconfirm -- "$PKG_FILE"
