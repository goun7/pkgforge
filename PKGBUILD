# Maintainer: goun7 <https://github.com/goun7/pkgforge>
pkgname=pkgforge
pkgver=1.1.0
pkgrel=1
pkgdesc="Modern .deb/.rpm package converter, safety analyzer, and lifecycle manager for Arch Linux"
arch=('any')
url="https://github.com/goun7/pkgforge"
license=('GPL-3.0-or-later')
depends=(
    'python'
    'pacman'
    'fakeroot'
    'libarchive'
)
makedepends=(
    'git'
    'python-build'
    'python-installer'
    'python-setuptools'
    'python-wheel'
)
optdepends=(
    'python-pyqt6: GUI interface (pkgforge gui)'
    'python-pyqt6-sip: GUI interface'
    'namcap: Static package analysis'
    'bubblewrap: Build sandbox isolation'
    'debtap: Legacy DEB conversion fallback'
    'rpmextract: RPM extraction support'
    'distrobox: Container fallback support'
    'clamav: Malware scanning'
    'trivy: OCI image security scanning'
    'xdelta3: Binary delta updates'
    'gnupg: Package signing'
)
provides=('pkgforge')
conflicts=('pkgforge')
backup=('etc/pkgforge.conf')
# NOTE: Tag v1.1.0 must exist in the repo before building this PKGBUILD.
# Update sha256sums once the release tarball is published.
source=("$pkgver.tar.gz::https://github.com/goun7/pkgforge/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

prepare() {
    cd "$srcdir/pkgforge-$pkgver"
    # No special prepare needed
}

build() {
    cd "$srcdir/pkgforge-$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "$srcdir/pkgforge-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl

    # Remove __pycache__ directories (bytecode — unnecessary in packages)
    find "$pkgdir" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

    # Desktop entry & Icon installation (if data files exist)
    if [ -f data/pkgforge.desktop ]; then
        install -Dm644 data/pkgforge.desktop "$pkgdir/usr/share/applications/org.pkgforge.app.desktop"
    fi
    if [ -f data/pkgforge.svg ]; then
        install -Dm644 data/pkgforge.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/pkgforge.svg"
    fi

    # Install config file
    install -Dm644 /dev/null "$pkgdir/etc/pkgforge.conf"

    # Install systemd timer for delta auto-updates
    if [ -f data/pkgforge-delta.service ]; then
        install -Dm644 data/pkgforge-delta.service "$pkgdir/usr/lib/systemd/system/pkgforge-delta.service"
        install -Dm644 data/pkgforge-delta.timer "$pkgdir/usr/lib/systemd/system/pkgforge-delta.timer"
    fi
}
