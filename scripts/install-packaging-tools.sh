#!/usr/bin/env bash
# PkgForge — Packaging build-dependency installer.
#
# Installs everything needed to BUILD the distributable package formats
# (Flatpak, AppImage) and the delta-update toolchain. Idempotent: already
# present pieces are skipped. Run after the base install, or standalone:
#
#   sudo ./scripts/install-packaging-tools.sh
#
# What it installs:
#   - flatpak + flatpak-builder   (pacman)  -> build the Flatpak
#   - xdelta3                     (pacman)  -> binary delta updates
#   - appimagetool                (GitHub)  -> build the AppImage
#   - org.kde.Platform/Sdk 6.7    (flathub) -> Flatpak runtime/SDK

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "❌ This installer requires administrative privileges (root/sudo)."
    echo "   Usage: sudo ./scripts/install-packaging-tools.sh"
    exit 1
fi

echo "📦 PkgForge — installing packaging build dependencies..."

# ── 1. pacman packages ─────────────────────────────────────────
# flatpak-builder builds the Flatpak; xdelta3 powers delta updates.
echo "🔧 pacman: flatpak flatpak-builder xdelta3"
pacman -S --needed --noconfirm flatpak flatpak-builder xdelta3 \
    || echo "⚠️  Some pacman packages failed to install (check mirrors/DB)."

# ── 2. appimagetool (not in pacman; GitHub release binary) ─────
# Pinned release + sha256: "continuous" is an untagged moving target and a
# supply-chain risk (root downloads it blind). Pin tag 1.9.0 x86_64.
if command -v appimagetool >/dev/null 2>&1; then
    echo "✅ appimagetool already present: $(command -v appimagetool)"
else
    ARCH="$(uname -m)"
    TAG="1.9.0"
    URL="https://github.com/AppImage/appimagetool/releases/download/${TAG}/appimagetool-${ARCH}.AppImage"
    case "${ARCH}" in
        x86_64)
            EXPECTED_SHA256="46fdd785094c7f6e545b61afcfb0f3d98d8eab243f644b4b17698c01d06083d1"
            ;;
        *)
            EXPECTED_SHA256=""
            ;;
    esac
    echo "⬇️  appimagetool: $URL"
    if curl -fsSL -o /usr/local/bin/appimagetool "$URL"; then
        if [ -n "$EXPECTED_SHA256" ]; then
            ACTUAL_SHA256="$(sha256sum /usr/local/bin/appimagetool | awk '{print $1}')"
            if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
                echo "❌ appimagetool sha256 mismatch (expected $EXPECTED_SHA256, got $ACTUAL_SHA256)"
                rm -f /usr/local/bin/appimagetool
                exit 1
            fi
        else
            echo "⚠️  No pinned sha256 for arch ${ARCH} — skipping integrity check"
        fi
        chmod 755 /usr/local/bin/appimagetool
        echo "✅ appimagetool ${TAG} installed to /usr/local/bin/appimagetool"
        echo "   NOTE: it is itself an AppImage. If FUSE is unavailable run it as:"
        echo "         appimagetool --appimage-extract-and-run ..."
    else
        echo "⚠️  appimagetool download failed (network?). Install manually from:"
        echo "    $URL"
    fi
fi

# ── 3. Flatpak runtime + SDK (large, first time only) ──────────
# The manifest targets org.kde.Platform / org.kde.Sdk 6.7.
if command -v flatpak >/dev/null 2>&1; then
    echo "🧩 Adding flathub remote (if missing) and installing KDE runtime/SDK 6.7..."
    flatpak remote-add --if-not-exists flathub \
        https://flathub.org/repo/flathub.flatpakrepo || true
    flatpak install -y --noninteractive flathub \
        org.kde.Platform//6.7 org.kde.Sdk//6.7 \
        || echo "⚠️  Flatpak runtime/SDK install failed (needed only to build the Flatpak)."
else
    echo "⚠️  flatpak CLI missing — skipping runtime/SDK install."
fi

echo ""
echo "✅ Packaging build dependencies ready."
echo "   Build Flatpak : flatpak-builder --force-clean build-flatpak packaging/flatpak/org.pkgforge.app.yml"
echo "   Build AppImage: bash packaging/appimage/build-appimage.sh"
