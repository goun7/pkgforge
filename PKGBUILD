# Maintainer: PkgForge Contributors <https://github.com/pkgforge/pkgforge>
pkgname=pkgforge-git
pkgver=1.0.0.r0.g1234567
pkgrel=1
pkgdesc="Modern .deb/.rpm package converter, safety analyzer, and lifecycle manager for Arch Linux"
arch=('any')
url="https://github.com/pkgforge/pkgforge"
license=('GPL-3.0-or-later')
depends=(
    'python'
    'python-pyqt6'
    'python-pyqt6-sip'
    'namcap'
    'fakeroot'
    'bubblewrap'
    'libarchive'
)
optdepends=(
    'debtap: Legacy DEB conversion fallback support'
    'rpmextract: RPM extraction support'
    'distrobox: Container fallback support'
)
provides=('pkgforge')
conflicts=('pkgforge')
source=("git+https://github.com/pkgforge/pkgforge.git")
sha256sums=('SKIP')

pkgver() {
    cd "$srcdir/pkgforge"
    git describe --long --tags 2>/dev/null | sed 's/^v//;s/\([^-]*-g\)/r\1/;s/-/./g' || echo "1.0.0"
}

package() {
    cd "$srcdir/pkgforge"
    python -m build --wheel --no-isolation
    python -m installer --destdir="$pkgdir" dist/*.whl

    # Desktop entry & Icon installation
    install -Dm644 data/pkgforge.desktop "$pkgdir/usr/share/applications/org.pkgforge.app.desktop"
    install -Dm644 data/pkgforge.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/pkgforge.svg"
}
