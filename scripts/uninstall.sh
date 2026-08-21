#!/usr/bin/env bash
# PkgForge — Automated System Uninstaller

set -euo pipefail

echo "🗑️ PkgForge — Starting System Uninstallation..."

if [ "$EUID" -ne 0 ]; then
    echo "❌ This uninstaller requires administrative privileges (root/sudo)."
    echo "   Usage: sudo ./scripts/uninstall.sh"
    exit 1
fi

# Stop and remove the auto-update systemd timer/service if present
if [ -f /etc/systemd/system/pkgforge-auto-update.timer ]; then
    echo "⏱️  Removing auto-update systemd timer/service..."
    systemctl stop pkgforge-auto-update.timer 2>/dev/null || true
    systemctl disable pkgforge-auto-update.timer 2>/dev/null || true
    rm -f /etc/systemd/system/pkgforge-auto-update.timer
    rm -f /etc/systemd/system/pkgforge-auto-update.service
    systemctl daemon-reload 2>/dev/null || true
fi
rm -f /usr/local/bin/pkgforge-auto-update.sh

echo "⚙️  Removing binary wrapper: /usr/local/bin/pkgforge"
rm -f /usr/local/bin/pkgforge

echo "📂 Removing application files: /usr/lib/pkgforge"
rm -rf /usr/lib/pkgforge

echo "🖥️  Removing desktop launcher entry..."
rm -f /usr/share/applications/pkgforge.desktop
rm -f /usr/share/applications/org.pkgforge.app.desktop
rm -f /usr/share/applications/archpkgporter.desktop
rm -f /home/*/.local/share/applications/pkgforge.desktop 2>/dev/null || true
rm -f /home/*/.local/share/applications/archpkgporter.desktop 2>/dev/null || true

echo "🎨 Removing application icon: /usr/share/icons/hicolor/scalable/apps/pkgforge.svg"
rm -f /usr/share/icons/hicolor/scalable/apps/pkgforge.svg

echo "🔐 Removing polkit policy..."
rm -f /usr/share/polkit-1/actions/org.pkgforge.app.policy

echo "⌨️  Removing shell completion scripts..."
rm -f /usr/share/bash-completion/completions/pkgforge
rm -f /usr/share/zsh/site-functions/_pkgforge

update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true

echo "✅ PkgForge has been successfully uninstalled from your system."
echo "   NOTE: User config/history in ~/.config/pkgforge was preserved."
