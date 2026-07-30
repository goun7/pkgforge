#!/bin/bash
# PkgForge — Desktop integration installer.
#
# Installs the .desktop file, SVG icon, and MIME associations
# so PkgForge appears in the application menu and can open
# .deb/.rpm files via file manager.
#
# Usage: bash install_desktop.sh [--uninstall]

set -euo pipefail

APP_NAME="pkgforge"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"

DESKTOP_FILE="${DATA_DIR}/${APP_NAME}.desktop"
SVG_ICON="${DATA_DIR}/${APP_NAME}.svg"

USER_APP_DIR="${HOME}/.local/share/applications"
USER_ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

# ── Uninstall ────────────────────────────────────────────────────

if [[ "${1:-}" == "--uninstall" ]]; then
    echo "🗑️  PkgForge masaüstü entegrasyonu kaldırılıyor..."
    rm -f "${USER_APP_DIR}/${APP_NAME}.desktop"
    rm -f "${USER_ICON_DIR}/${APP_NAME}.svg"

    # PNG icons
    for size in 48 128 256; do
        rm -f "${HOME}/.local/share/icons/hicolor/${size}x${size}/apps/${APP_NAME}.png"
    done

    xdg-desktop-menu forceupdate 2>/dev/null || true
    gtk-update-icon-cache -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
    update-desktop-database "${USER_APP_DIR}" 2>/dev/null || true

    echo "✓ Kaldırma tamamlandı."
    exit 0
fi

# ── Install ──────────────────────────────────────────────────────

echo "🔧 PkgForge masaüstü entegrasyonu kuruluyor..."

# Check required files
if [[ ! -f "${DESKTOP_FILE}" ]]; then
    echo "❌ Desktop dosyası bulunamadı: ${DESKTOP_FILE}"
    exit 1
fi

if [[ ! -f "${SVG_ICON}" ]]; then
    echo "❌ İkon dosyası bulunamadı: ${SVG_ICON}"
    exit 1
fi

# Create directories
mkdir -p "${USER_APP_DIR}"
mkdir -p "${USER_ICON_DIR}"

# Install SVG icon
echo "  📎 SVG ikon kuruluyor..."
cp "${SVG_ICON}" "${USER_ICON_DIR}/${APP_NAME}.svg"

# Generate PNG icons if rsvg-convert is available
if command -v rsvg-convert &>/dev/null; then
    echo "  🖼️  PNG ikonları oluşturuluyor..."
    for size in 48 128 256; do
        PNG_DIR="${HOME}/.local/share/icons/hicolor/${size}x${size}/apps"
        mkdir -p "${PNG_DIR}"
        rsvg-convert -w ${size} -h ${size} "${SVG_ICON}" -o "${PNG_DIR}/${APP_NAME}.png"
        echo "    ✓ ${size}x${size}"
    done
else
    echo "  ⚠ rsvg-convert bulunamadı, PNG ikonları atlanıyor (yüklemek: pacman -S librsvg)"
fi

# Install desktop file (update Exec path)
echo "  📋 Desktop dosyası kuruluyor..."
sed "s|Exec=python3 .*main.py|Exec=python3 ${SCRIPT_DIR}/main.py|g" \
    "${DESKTOP_FILE}" > "${USER_APP_DIR}/${APP_NAME}.desktop"
chmod +x "${USER_APP_DIR}/${APP_NAME}.desktop"

# Validate desktop file
if command -v desktop-file-validate &>/dev/null; then
    desktop-file-validate "${USER_APP_DIR}/${APP_NAME}.desktop" 2>/dev/null || true
fi

# Update caches
echo "  🔄 Önbellekler güncelleniyor..."
xdg-desktop-menu forceupdate 2>/dev/null || true
gtk-update-icon-cache -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
update-desktop-database "${USER_APP_DIR}" 2>/dev/null || true

echo ""
echo "✅ PkgForge masaüstü entegrasyonu tamamlandı!"
echo ""
echo "  🖥️  Uygulama menüsünde 'PkgForge' arayın"
echo "  📂  .deb/.rpm dosyalarına sağ tıklayıp PkgForge ile açabilirsiniz"
echo ""
echo "  Kaldırmak için: bash ${BASH_SOURCE[0]} --uninstall"
