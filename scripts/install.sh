#!/usr/bin/env bash
# PkgForge — Automated System Installer for Arch Linux / CachyOS

set -euo pipefail

# Root / sudo check
if [ "$EUID" -ne 0 ]; then
    echo "❌ This installer requires administrative privileges (root/sudo) to write to system directories."
    echo "   Usage: sudo ./scripts/install.sh"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Read version from pyproject.toml (single source of truth) without
# importing project code as root (import executes arbitrary file content).
VERSION="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$PROJECT_DIR/pyproject.toml" | head -1)"
VERSION="${VERSION:-unknown}"
echo "📦 PkgForge v$VERSION — Starting System Installation..."

INSTALL_DIR="/usr/lib/pkgforge"

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

# Packaging build dependencies (Flatpak / AppImage / delta) — installed
# directly so package builds work out of the box. Best-effort: a failure
# here must not abort the base application install.
echo "🔧 Installing packaging build dependencies (flatpak-builder, xdelta3)..."
pacman -S --needed --noconfirm flatpak-builder xdelta3 2>/dev/null \
    || echo "⚠️  flatpak-builder/xdelta3 kurulamadı (opsiyonel; paket derlemek için)"
# Full packaging toolchain (appimagetool + Flatpak KDE runtimes).
if [ -x "$PROJECT_DIR/scripts/install-packaging-tools.sh" ]; then
    "$PROJECT_DIR/scripts/install-packaging-tools.sh" \
        || echo "⚠️  Tam paketleme araç zinciri kurulumunda sorun (opsiyonel)"
fi

# 1. Copy the application tree to a stable system location so the launcher
#    keeps working even if the git clone is moved or deleted.
echo "📂 Installing application files: $INSTALL_DIR"
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
# Copy everything except VCS metadata, virtualenvs, caches, tests and docs —
# tests/docs/CI artefacts have no business inside /usr/lib.
tar -C "$PROJECT_DIR" \
    --exclude=.git --exclude=.venv --exclude=__pycache__ \
    --exclude=.mypy_cache --exclude=.pytest_cache --exclude=.hypothesis \
    --exclude=.ruff_cache --exclude=build --exclude=dist \
    --exclude="*.egg-info" --exclude=.freebuff --exclude=utest \
    --exclude=tests --exclude=docs --exclude=.github \
    --exclude=htmlcov --exclude=.coverage \
    --exclude=node_modules --exclude=target \
    --exclude="*.deb" --exclude="*.rpm" --exclude="*.pkg.tar.*" \
    -cf - . | tar -C "$INSTALL_DIR" -xf -

# 2. Binary wrapper installation
echo "⚙️  Installing executable wrapper: /usr/local/bin/pkgforge"
cat << EOF > /usr/local/bin/pkgforge
#!/usr/bin/env bash
exec python3 "$INSTALL_DIR/main.py" "\$@"
EOF
chmod 755 /usr/local/bin/pkgforge

# 3. Desktop launcher entry
echo "🖥️  Installing desktop entry: /usr/share/applications/pkgforge.desktop"
mkdir -p /usr/share/applications
cp "$PROJECT_DIR/data/pkgforge.desktop" /usr/share/applications/pkgforge.desktop
chmod 644 /usr/share/applications/pkgforge.desktop

# 4. Icon installation
echo "🎨 Installing application icon: /usr/share/icons/hicolor/scalable/apps/pkgforge.svg"
mkdir -p /usr/share/icons/hicolor/scalable/apps
cp "$PROJECT_DIR/data/pkgforge.svg" /usr/share/icons/hicolor/scalable/apps/pkgforge.svg
chmod 644 /usr/share/icons/hicolor/scalable/apps/pkgforge.svg

# 5. Polkit policies.
# Faz 14 + SEC: yalnizca konsolide helper policy kurulur. Eski app.policy
# /usr/bin/pacman'a genel polkit yetkisi veriyordu (keyfi pacman calistirma
# yuzu) ve kaldirildi; tum root islemleri pkgforge-privileged.sh'tan gecer.
mkdir -p /usr/share/polkit-1/actions
rm -f /usr/share/polkit-1/actions/org.pkgforge.app.policy
if [ -f "$PROJECT_DIR/packaging/polkit/org.pkgforge.helper.policy" ]; then
    echo "🔐 Installing polkit policy: /usr/share/polkit-1/actions/org.pkgforge.helper.policy"
    cp "$PROJECT_DIR/packaging/polkit/org.pkgforge.helper.policy" /usr/share/polkit-1/actions/org.pkgforge.helper.policy
    chmod 644 /usr/share/polkit-1/actions/org.pkgforge.helper.policy
fi

# 5b. Privileged helper scripts — pkexec bunlari root sahipli 0755 olarak
# arar; kaynak agacindaki sahipli betikler polkit tarafindan reddedilir.
echo "🔐 Installing privileged helpers: /usr/share/pkgforge/scripts/"
mkdir -p /usr/share/pkgforge/scripts
for h in install_helper.sh pkgforge-privileged.sh; do
    if [ -f "$PROJECT_DIR/scripts/$h" ]; then
        cp "$PROJECT_DIR/scripts/$h" "/usr/share/pkgforge/scripts/$h"
        chmod 755 "/usr/share/pkgforge/scripts/$h"
    fi
done

# 6. Shell completion installation
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

echo "✅ PkgForge v$VERSION has been successfully installed on your system!"
echo "   Launch GUI: pkgforge gui (or from your Application Launcher)"
echo "   Run CLI:    pkgforge"
