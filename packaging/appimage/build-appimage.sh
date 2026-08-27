#!/usr/bin/env bash
# PkgForge — AppImage build script (v2.0.0, DENEYSEL baslangic noktasi).
#
# Bir AppDir agaci kurup appimagetool ile tek-dosya AppImage uretir.
# PkgForge bir Python uygulamasi oldugu icin AppDir icine yorumlayici ve
# bagimliliklari tasinir; sistem araclarina (pacman, polkit) erisim host
# uzerinden saglanir (AppImage disinda calisir).
#
# Gereksinimler:
#   - appimagetool   (https://github.com/AppImage/appimagetool)
#   - python3 + venv, build, installer
#   - (opsiyonel) linuxdeploy + linuxdeploy-plugin-python
#
# Kullanim:
#   bash packaging/appimage/build-appimage.sh
#
# Cikti: dist/PkgForge-<surum>-x86_64.AppImage
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VERSION="$(python3 -c 'import config; print(config.APP_VERSION)')"
ARCH="$(uname -m)"
APPDIR="dist/AppDir"

echo "==> PkgForge $VERSION AppImage ($ARCH)"

command -v appimagetool >/dev/null 2>&1 || {
  echo "HATA: appimagetool bulunamadi. PATH'e ekleyin." >&2
  exit 1
}

# ── 1. Wheel insa et ────────────────────────────────────────────
echo "==> Wheel insa ediliyor"
python3 -m build --wheel --no-isolation --outdir dist/wheel

# ── 2. AppDir iskeleti ──────────────────────────────────────────
echo "==> AppDir hazirlaniyor"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps" \
         "$APPDIR/usr/share/metainfo"

# Wheel'i AppDir icindeki izole bir venv'e kur.
python3 -m venv "$APPDIR/usr"
"$APPDIR/usr/bin/pip" install --no-cache-dir dist/wheel/*.whl

# Launcher + metadata.
install -Dm755 packaging/appimage/AppRun "$APPDIR/AppRun"
install -Dm644 packaging/appimage/pkgforge.desktop \
  "$APPDIR/usr/share/applications/pkgforge.desktop"
cp "$APPDIR/usr/share/applications/pkgforge.desktop" "$APPDIR/pkgforge.desktop"
install -Dm644 data/pkgforge.svg \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps/pkgforge.svg"
ln -sf "usr/share/icons/hicolor/scalable/apps/pkgforge.svg" "$APPDIR/pkgforge.svg"
install -Dm644 data/org.pkgforge.app.metainfo.xml \
  "$APPDIR/usr/share/metainfo/org.pkgforge.app.metainfo.xml"

# ── 3. AppImage uret ────────────────────────────────────────────
echo "==> appimagetool calistiriliyor"
ARCH="$ARCH" appimagetool "$APPDIR" "dist/PkgForge-$VERSION-$ARCH.AppImage"

echo "==> TAMAM: dist/PkgForge-$VERSION-$ARCH.AppImage"
