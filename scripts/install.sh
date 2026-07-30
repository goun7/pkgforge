#!/usr/bin/env bash
# PkgForge — Automated System Installer for Arch Linux / CachyOS

set -e

echo "📦 PkgForge v1.0.0 — Starting System Installation..."

# Root / sudo check
if [ "$EUID" -ne 0 ]; then
    echo "❌ This installer requires administrative privileges (root/sudo) to write to system directories."
    echo "   Usage: sudo ./scripts/install.sh"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Clean any stale or duplicate desktop files
rm -f /usr/share/applications/org.pkgforge.app.desktop
rm -f /usr/share/applications/archpkgporter.desktop
rm -f /home/*/.local/share/applications/pkgforge.desktop 2>/dev/null || true
rm -f /home/*/.local/share/applications/archpkgporter.desktop 2>/dev/null || true

# Dependencies check
echo "🔍 Checking system dependencies..."
python3 -c "import PyQt6" 2>/dev/null || {
    echo "⚠️ PyQt6 not found. Installing system dependencies: pacman -S python-pyqt6 python-pyqt6-sip"
    pacman -S --needed --noconfirm python-pyqt6 python-pyqt6-sip libarchive fakeroot bubblewrap || true
}

# 1. Binary wrapper installation
echo "⚙️  Installing executable wrapper: /usr/local/bin/pkgforge"
cat << EOF > /usr/local/bin/pkgforge
#!/usr/bin/env bash
exec python3 "$PROJECT_DIR/main.py" "\$@"
EOF
chmod +x /usr/local/bin/pkgforge

# 2. Desktop launcher entry
echo "🖥️  Installing desktop entry: /usr/share/applications/pkgforge.desktop"
mkdir -p /usr/share/applications
cp "$PROJECT_DIR/data/pkgforge.desktop" /usr/share/applications/pkgforge.desktop
chmod 644 /usr/share/applications/pkgforge.desktop

# 3. Icon installation
echo "🎨 Installing application icon: /usr/share/icons/hicolor/scalable/apps/pkgforge.svg"
mkdir -p /usr/share/icons/hicolor/scalable/apps
cp "$PROJECT_DIR/data/pkgforge.svg" /usr/share/icons/hicolor/scalable/apps/pkgforge.svg
chmod 644 /usr/share/icons/hicolor/scalable/apps/pkgforge.svg

# 4. Shell completion installation
if [ -d "$PROJECT_DIR/data/completions" ]; then
    echo "⌨️  Installing shell completion scripts..."
    mkdir -p /usr/share/bash-completion/completions
    cp "$PROJECT_DIR/data/completions/pkgforge.bash" /usr/share/bash-completion/completions/pkgforge 2>/dev/null || true

    mkdir -p /usr/share/zsh/site-functions
    cp "$PROJECT_DIR/data/completions/_pkgforge" /usr/share/zsh/site-functions/_pkgforge 2>/dev/null || true
fi

# Update desktop database
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true

echo "✅ PkgForge has been successfully installed on your system!"
echo "   Launch GUI: pkgforge gui (or from your Application Launcher)"
echo "   Run CLI:    pkgforge"
