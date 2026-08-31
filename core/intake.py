"""PkgForge - Evrensel girdi katmani (universal intake).

Bir dosya/klasorun turunu siniflandiran ve dogru isleyiciye yonlendiren TEK
dogruluk kaynagi. UI-bagimsizdir: hem PyQt6 on yuzu hem Tauri/web sidecar
ayni siniflandiriciyi kullanir. Mevcut donusturuculer degismez, yeniden kullanilir.

Siniflandirma uc asamada yapilir (ucuzdan pahaliya):
1. Sonek (hizli yol): .deb, .rpm, .AppImage, .flatpakref, .pkg.tar.*
2. Magic bytes (uzantisiz/yaniltici): DEB=!<arch>, RPM=edabeedb (hex)
3. Icerik sezgisi (tarball): arsivi TAM ACMADAN listele.

.tar.gz karari (intent-driven): icerikte build-sistemi markeri varsa
SOURCE_TARBALL, hazir binary yerlesimi varsa BINARY_TARBALL, ikisi de veya
celiskili ise ambiguous=True ile UNKNOWN doner (UI kullaniciya sorar).
"""

from __future__ import annotations

import logging
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)


class FileType(str, Enum):
    """Bilinen girdi turleri."""

    DEB = "deb"
    RPM = "rpm"
    APPIMAGE = "appimage"
    FLATPAKREF = "flatpakref"
    SOURCE_TARBALL = "source_tarball"
    BINARY_TARBALL = "binary_tarball"
    ARCH_PKG = "arch_pkg"
    SOURCE_DIR = "source_dir"
    UNKNOWN = "unknown"


@dataclass
class IntakeResult:
    """Siniflandirma sonucu.

    actions alani Alt Proje 2 (eylem modeli) icin hazirlanir; bu katmanda
    sadece onerilen eylem adlarini tasir.
    """

    file_type: FileType
    path: Path
    confidence: float = 1.0
    reason: str = ""
    build_system: str | None = None
    ambiguous: bool = False
    actions: list[str] = field(default_factory=list)


# -- Sabitler ----------------------------------------------------
_DEB_MAGIC = b"!<arch>"
_RPM_MAGIC = bytes.fromhex("edabeedb")
_ZIP_MAGIC = bytes.fromhex("504b0304")
_XZ_MAGIC = bytes.fromhex("fd377a585a00")
_GZ_MAGIC = bytes.fromhex("1f8b")
_BZ2_MAGIC = b"BZh"
_ZST_MAGIC = bytes.fromhex("28b52ffd")

# Arch paket sonekleri (.pkg.tar.zst / .pkg.tar.xz / .pkg.tar.gz)
_ARCH_PKG_TAIL = (".pkg.tar.zst", ".pkg.tar.xz", ".pkg.tar.gz", ".pkg.tar")

# Tarball olarak kabul edilen sonekler
_TARBALL_SUFFIXES = (
    ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2",
    ".tar.zst", ".tar", ".zip",
)

# Build-sistemi markerlari (oncelik sirasiyla): (dosya adi, sistem)
_BUILD_MARKERS: tuple[tuple[str, str], ...] = (
    ("Cargo.toml", "cargo"),
    ("CMakeLists.txt", "cmake"),
    ("meson.build", "meson"),
    ("pyproject.toml", "python"),
    ("setup.py", "python"),
    ("configure", "autotools"),
    ("Makefile", "make"),
    ("makefile", "make"),
    ("go.mod", "go"),
    ("package.json", "node"),
)


# -- Yardimcilar -------------------------------------------------
def _read_magic(path: Path, n: int = 8) -> bytes:
    """Ilk n bayti okur; okunamazsa bos bytes doner."""
    try:
        with path.open("rb") as f:
            return f.read(n)
    except OSError as exc:
        log.debug("magic okunamadi (%s): %s", path, exc)
        return b""


def _has_tarball_suffix(name_lower: str) -> bool:
    return any(name_lower.endswith(s) for s in _TARBALL_SUFFIXES)


def _is_arch_pkg_name(name_lower: str) -> bool:
    return any(name_lower.endswith(t) for t in _ARCH_PKG_TAIL)


def _list_archive(path: Path) -> list[str] | None:
    """Arsiv girdilerini TAM ACMADAN listeler; bozuksa None doner."""
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as zf:
                return zf.namelist()
        with tarfile.open(path, "r:*") as tf:
            return tf.getnames()
    except (tarfile.TarError, zipfile.BadZipFile, OSError, EOFError) as exc:
        log.debug("arsiv listelenemedi (%s): %s", path, exc)
        return None


def _basenames(names: list[str]) -> set[str]:
    return {n.rstrip("/").split("/")[-1] for n in names if n}


def detect_build_system(names: list[str]) -> str | None:
    """Girdi adlarindan build sistemini algilar (yoksa None)."""
    base = _basenames(names)
    for marker, system in _BUILD_MARKERS:
        if marker in base:
            return system
    return None


def looks_like_binary_layout(names: list[str]) -> bool:
    """Hazir binary yerlesimi mi (usr/bin veya .desktop)?"""
    for n in names:
        ln = n.lower().lstrip("./")
        if "usr/bin/" in ln or ln.startswith("usr/bin/"):
            return True
        if ln.endswith(".desktop"):
            return True
    return False


# -- Ana siniflandirici -----------------------------------------
def classify(path: Path) -> IntakeResult:
    """Bir yolun turunu siniflandirir."""
    path = Path(path)
    if path.is_dir():
        return _classify_dir(path)
    if not path.is_file():
        return IntakeResult(FileType.UNKNOWN, path, 0.0, "dosya bulunamadi")

    name_lower = path.name.lower()

    # 1) Sonek - hizli yol
    if name_lower.endswith(".deb"):
        return IntakeResult(FileType.DEB, path, 0.9, "uzanti .deb",
                            actions=["convert", "install"])
    if name_lower.endswith(".rpm"):
        return IntakeResult(FileType.RPM, path, 0.9, "uzanti .rpm",
                            actions=["convert", "install"])
    if name_lower.endswith(".appimage"):
        return IntakeResult(FileType.APPIMAGE, path, 0.9, "uzanti .AppImage",
                            actions=["convert"])
    if name_lower.endswith(".flatpakref"):
        return IntakeResult(FileType.FLATPAKREF, path, 0.9, "uzanti .flatpakref",
                            actions=["convert"])
    if _is_arch_pkg_name(name_lower):
        return IntakeResult(FileType.ARCH_PKG, path, 0.95, "Arch paket uzantisi",
                            actions=["install"])

    # 2) Magic bytes - uzantisiz/yaniltici dosyalar
    magic = _read_magic(path)
    if magic.startswith(_DEB_MAGIC):
        return IntakeResult(FileType.DEB, path, 0.8, "magic !<arch>",
                            actions=["convert", "install"])
    if magic.startswith(_RPM_MAGIC):
        return IntakeResult(FileType.RPM, path, 0.8, "magic rpm",
                            actions=["convert", "install"])

    # 3) Tarball icerik sezgisi
    if _has_tarball_suffix(name_lower) or magic.startswith(
            (_GZ_MAGIC, _XZ_MAGIC, _BZ2_MAGIC, _ZST_MAGIC, _ZIP_MAGIC)):
        return _classify_tarball(path)

    return IntakeResult(FileType.UNKNOWN, path, 0.0, "tanimanamayan tur")


def _classify_dir(path: Path) -> IntakeResult:
    """Bir klasoru kaynak agaci olarak siniflandirir."""
    try:
        entries = [p.name for p in path.iterdir()]
    except OSError as exc:
        return IntakeResult(FileType.UNKNOWN, path, 0.0, "klasor okunamadi: " + str(exc))
    system = detect_build_system(entries)
    if system:
        return IntakeResult(FileType.SOURCE_DIR, path, 0.85,
                            "kaynak klasoru (" + system + ")", build_system=system,
                            actions=["build", "install"])
    return IntakeResult(FileType.UNKNOWN, path, 0.2,
                        "klasorde build sistemi bulunamadi", ambiguous=True)


def _classify_tarball(path: Path) -> IntakeResult:
    """Bir tarballin kaynak mi binary mi olduguna icerikten karar verir."""
    names = _list_archive(path)
    if names is None:
        return IntakeResult(FileType.UNKNOWN, path, 0.0,
                            "arsiv okunamadi veya bozuk")
    if any(n.rstrip("/").split("/")[-1] == ".PKGINFO" for n in names):
        return IntakeResult(FileType.ARCH_PKG, path, 0.9, ".PKGINFO bulundu",
                            actions=["install"])
    system = detect_build_system(names)
    binary = looks_like_binary_layout(names)
    if system and not binary:
        return IntakeResult(FileType.SOURCE_TARBALL, path, 0.85,
                            "build sistemi: " + system, build_system=system,
                            actions=["build", "install"])
    if binary and not system:
        return IntakeResult(FileType.BINARY_TARBALL, path, 0.7,
                            "hazir binary yerlesimi", actions=["wrap", "install"])
    if system and binary:
        return IntakeResult(FileType.UNKNOWN, path, 0.4,
                            "hem kaynak hem binary isaretleri", build_system=system,
                            ambiguous=True, actions=["build", "wrap"])
    return IntakeResult(FileType.UNKNOWN, path, 0.2, "icerik tanimlanamadi",
                        ambiguous=True)


# -- Binary tarball -> Arch paketi (PKGBUILD uretimi) -----------
def generate_binary_pkgbuild(
    name: str,
    version: str,
    tarball_name: str,
    description: str = "",
    exec_relpath: str | None = None,
    extract: bool = True,
    depends: list[str] | None = None,
    url: str = "",
    license_id: str = "unknown",
    sha256: str = "SKIP",
) -> str:
    """Hazir binary icerigi Arch paketine sarmak icin PKGBUILD uretir.

    tarball_name makepkg source olarak kullanilir. sha256 verilirse
    gercek tarball ozeti yazilir; aksi halde SKIP (yerel dosya icin
    makepkg zaten ozeti dogrulayamaz, bu yuzden varsayilan SKIP'tir).
    url bos degilse PKGBUILD url= alanina yazilir; bos ise upstream
    bilinmiyorsa "unknown" dokumantasyon degeri kullanilir (namcap
    error-no-url onlemi).
    exec_relpath verilirse /usr/bin altina sarmalayici kurulur.
    license_id, kaynakta bilinen lisans tanimlayicisidir; binary
    sarimlarda lisans bilinmediginden varsayilan "unknown"dur.
    extract=True (varsayilan) ise tarball icerigi tar -xf ile dogrudan
    pkgdir/opt/<name> altina acilir; tarball dosyasinin kendisi pakete
    girmez. Boylece cp -r "$srcdir"/. yuzunden kaynak tarball pakete
    kopyalanmasi (dangling-symlink + elffile-in-questionable-dirs)
    onlenir. extract=False ise $srcdir icerigi tarball haric kopyalanir.
    depends verilirse paket bagimliliklari olarak eklenir; verilmezse
    glib2 + cairo varsayilir (namcap dependency-detected-not-included
    azaltmak icin minimum guvenli set).
    """
    desc = description.replace(chr(34), "") or (name + " (PkgForge ile sarildi)")
    if depends is None:
        depends = ["glib2", "cairo"]
    deps = " ".join('"' + d + '"' for d in depends)
    deps = "(" + deps + ")"
    lines = [
        "pkgname=" + name,
        "pkgver=" + version,
        "pkgrel=1",
        'pkgdesc="' + desc + '"',
        'arch=("x86_64")',
        'url="' + (url if url else "unknown") + '"',
        "license=('" + license_id + "')",
        "depends=" + deps,
        'source=("' + tarball_name + '")',
        'sha256sums=("' + (sha256 or "SKIP") + '")',
        "",
        "package() {"
    ]
    if extract:
        lines += [
            '    install -d "$pkgdir/opt/' + name + '"',
            '    tar -xf "$srcdir"/' + tarball_name + ' -C "$pkgdir/opt/' + name + '"',
        ]
    else:
        lines += [
            '    install -d "$pkgdir/opt/' + name + '"',
            '    shopt -s dotglob nullglob',
            '    for f in "$srcdir"/*; do',
            '      if [[ "$f" != *"' + tarball_name + '" ]]; then',
            '        cp -r "$f" "$pkgdir/opt/' + name + '"/;',
            '      fi',
            '    done',
        ]
    if exec_relpath:
        # /usr/bin wrapper: launch the app via /opt/<name>/<exec_relpath>
        lines += [
            '    install -d "$pkgdir/usr/bin"',
            '    cat > "$pkgdir/usr/bin/' + name + '" <<\'EOF\'',
            '#!/bin/sh',
            'exec /opt/' + name + '/' + exec_relpath + ' "$@"',
            'EOF',
            '    chmod +x "$pkgdir/usr/bin/' + name + '"',
            '    # .desktop file for application menu',
            '    install -d "$pkgdir/usr/share/applications"',
            '    cat > "$pkgdir/usr/share/applications/' + name + '.desktop" <<\'EOF\'',
            '[Desktop Entry]',
            'Name=' + name,
            'Exec=' + name,
            'Type=Application',
            'Terminal=false',
            'Categories=Utility;',
            'EOF',
        ]
    lines += ["}", ""]
    return chr(10).join(lines)


def find_binary_entrypoint(names: list[str]) -> str | None:
    """Binary yerlesimindeki ilk calistirilabilirin goreceli yolunu bulur."""
    for n in names:
        ln = n.lower().lstrip("./")
        if "usr/bin/" in ln:
            idx = ln.index("usr/bin/")
            return n[idx:]
    return None



# -- Kaynak tarball -> Arch paketi (PKGBUILD uretimi) -----------
# -- Dosya adindan isim/versiyon turetme ------------------------
def _sanitize_name(name: str) -> str:
    """Gecersiz karakterleri temizleyip gecerli bir pkgname uretir."""
    s = re.sub(r"[^a-zA-Z0-9@._+-]", "-", name).lower().strip("-.")
    return s or "paket"


def derive_name_version(stem: str) -> tuple[str, str]:
    """Bir dosya govdesinden (uzantisiz) isim ve versiyon tahmin eder.

    Ornekler:
        "foo-1.0"                 -> ("foo", "1.0")
        "node-v20.11.0-linux"     -> ("node", "20.11.0")
        "SomeApp_Linux_x86_64"    -> ("someapp-linux-x86-64", "0.0.1")
    """
    m = re.search(r"[-_]v?(\d+(?:\.\d+)+)", stem)
    if m:
        version = m.group(1)
        name = stem[: m.start()].strip("-_ ")
        if name:
            return _sanitize_name(name), version
    return _sanitize_name(stem), "0.0.1"


def find_top_level_dir(names: list[str]) -> str | None:
    """Arsiv girdilerinin paylastigi tek ust dizini bulur (yoksa None).

    Ornegin ["foo-1.0/src", "foo-1.0/README"] -> "foo-1.0".
    Kokte daginik dosyalar varsa None doner.
    """
    tops = {n.split("/")[0] for n in names if "/" in n}
    if len(tops) == 1:
        return tops.pop()
    return None


def _source_build_commands(build_system: str, binary_name: str | None = None):
    """Build sistemine gore (makedepends, build, install) komutlarini dondurur."""
    if build_system == "cmake":
        return (
            ["cmake", "gcc"],
            'cmake -B build -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release && cmake --build build',
            'DESTDIR="$pkgdir" cmake --install build',
        )
    if build_system == "meson":
        return (
            ["meson", "gcc"],
            'meson setup build --prefix=/usr --buildtype=release && meson compile -C build',
            'DESTDIR="$pkgdir" meson install -C build',
        )
    if build_system == "cargo":
        bn = binary_name or "main"
        return (
            ["rust", "cargo"],
            "cargo build --release --locked",
            'install -Dm755 target/release/' + bn + ' "$pkgdir/usr/bin/' + bn + '"',
        )
    if build_system == "autotools":
        return (
            ["gcc", "autoconf", "automake"],
            "./configure --prefix=/usr --sysconfdir=/etc && make",
            'make DESTDIR="$pkgdir" install',
        )
    if build_system == "python":
        return (
            ["python-build", "python-installer", "python-setuptools"],
            "python -m build --wheel --no-isolation",
            'python -m installer --destdir="$pkgdir" dist/*.whl',
        )
    if build_system == "node":
        return (
            ["nodejs", "npm"],
            "npm ci && npm run build",
            'mkdir -p "$pkgdir/usr/lib/$pkgname" && cp -r dist/. "$pkgdir/usr/lib/$pkgname/"',
        )
    if build_system == "go":
        gn = binary_name or "app"
        return (
            ["go"],
            "go build -o " + gn,
            'install -Dm755 ' + gn + ' "$pkgdir/usr/bin/' + gn + '"',
        )
    # varsayilan: duz make
    return (
        ["gcc"],
        "make",
        'make DESTDIR="$pkgdir" install',
    )


def generate_source_tarball_pkgbuild(
    name: str,
    version: str,
    tarball_name: str,
    top_dir: str | None,
    build_system: str,
    license_id: str = "unknown",
    description: str = "",
    binary_name: str | None = None,
    url: str = "",
    sha256: str = "SKIP",
) -> str:
    """Yerel kaynak tarballini derleyip paketleyen PKGBUILD uretir.

    Tarball PKGBUILD'in yanina kopyalanir; makepkg onu $srcdir'a acar ve
    build/package adimlari top_dir icinde calisir. url bos degilse
    upstream proje adresi olarak yazilir (namcap error-no-url onlemi);
    bilinmiyorsa "unknown" kullanilir. sha256 verilirse gercek tarball
    ozeti yazilir.
    """
    makedeps, build_cmds, install_cmds = _source_build_commands(build_system, binary_name)
    makedepends_str = " ".join("'" + d + "'" for d in makedeps)
    cd = 'cd "$srcdir/' + top_dir + '"' if top_dir else 'cd "$srcdir"'
    desc = description.replace(chr(34), "") or (name + " (PkgForge kaynak derleme)")
    lines = [
        "# Maintainer: PkgForge <noreply@pkgforge.app>",
        "",
        "pkgname=" + name,
        "pkgver=" + version,
        "pkgrel=1",
        'pkgdesc="' + desc + '"',
        'arch=("x86_64")',
        'url="' + (url if url else "unknown") + '"',
        "license=('" + license_id + "')",
        "depends=()",
        "makedepends=(" + makedepends_str + ")",
        'source=("' + tarball_name + '")',
        'sha256sums=("' + (sha256 or "SKIP") + '")',
        "",
        "build() {",
        "    " + cd,
        "    " + build_cmds,
        "}",
        "",
        "package() {",
        "    " + cd,
        "    " + install_cmds,
        "}",
        "",
    ]
    return chr(10).join(lines)