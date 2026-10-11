"""pkgforge core.intake dal-kesen testleri (LEED) — 7 fonksiyon.

Kapsanan fonksiyonlar: _basenames, _has_tarball_suffix, _is_arch_pkg_name,
_classify_dir, _classify_tarball, _sanitize_name, _source_build_commands.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — arsivler stdlib tarfile ile tmp_path'te uretilir,
         network/subprocess YOK; Path.iterdir hata yolu monkeypatch.
"""
import io
import re
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, ".")
from core.intake import (  # noqa: E402
    FileType, IntakeResult, _basenames, _classify_dir, _classify_tarball,
    _has_tarball_suffix, _is_arch_pkg_name, _sanitize_name,
    _source_build_commands,
)

_TARBALL_SUFFIXES = (
    ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2",
    ".tar.zst", ".tar", ".zip",
)
_ARCH_PKG_TAIL = (".pkg.tar.zst", ".pkg.tar.xz", ".pkg.tar.gz", ".pkg.tar")
_BUILD_MARKERS = (
    ("Cargo.toml", "cargo"), ("CMakeLists.txt", "cmake"), ("meson.build", "meson"),
    ("pyproject.toml", "python"), ("setup.py", "python"), ("configure", "autotools"),
    ("Makefile", "make"), ("makefile", "make"), ("go.mod", "go"),
    ("package.json", "node"),
)


def _make_tar(path: Path, names: list[str], mode: str = "w:gz") -> Path:
    """Stdlib tarfile ile sahte arsiv — her girdi bos dosya (network YOK)."""
    with tarfile.open(path, mode) as tf:
        for n in names:
            if n.endswith("/"):
                info = tarfile.TarInfo(n)
                info.type = tarfile.DIRTYPE
                tf.addfile(info)
            else:
                data = b"x"
                info = tarfile.TarInfo(n)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
    return path


# == _basenames ====================================================================================

@pytest.mark.parametrize("names,expected", [
    (["a/b/c.txt"], {"c.txt"}),
    (["a/b/c.txt", "d/e"], {"c.txt", "e"}),
    (["d/"], {"d"}),
    ([""], set()),
    ([], set()),
    (["f//g"], {"g"}),
    (["x", "x", "y"], {"x", "y"}),
    (["a/b/", "a/b"], {"b"}),
    ([" a/b c"], {"b c"}),
    (["深层/目录/文件"], {"文件"}),
])
def test_basenames(names, expected):
    """ORTAM: son bileşen; trailing slash ayiklanir; bos filtrelenir; tekrar erir."""
    assert _basenames(names) == expected


def test_basenames_set_doner():
    """ORTAM: donus tipi set (benzersiz)."""
    r = _basenames(["a/b", "c/b", "d/b"])
    assert isinstance(r, set)
    assert r == {"b"}


def test_basenames_bos_string_korunur():
    """ORTAM: 'if n' bos string elenir ama ' ' (bosluk) ELMEZ."""
    assert _basenames([" "]) == {" "}


# == _has_tarball_suffix ===========================================================================

@pytest.mark.parametrize("suffix", _TARBALL_SUFFIXES)
def test_tarball_suffix_hepsi_true(suffix):
    """ORTAM: tum kabul edilen sonekler True."""
    assert _has_tarball_suffix("paket" + suffix) is True


@pytest.mark.parametrize("name", [
    "paket.deb", "paket.rpm", "paket.appimage", "paket.flatpakref",
    "paket", "paket.tar.gz.bak", "paket.gz", "PAKET.TAR.GZ", "Tar.Gz",
    "", "pkg.tar.zst.old",
])
def test_tarball_suffix_negatif(name):
    """ORTAM: diger uzantilar/degisik-buyukharf False."""
    assert _has_tarball_suffix(name) is False


# == _is_arch_pkg_name =============================================================================

@pytest.mark.parametrize("tail", _ARCH_PKG_TAIL)
def test_arch_pkg_tail_hepsi_true(tail):
    """ORTAM: tum Arch paket sonekleri True."""
    assert _is_arch_pkg_name("firefox-120.0" + tail) is True


@pytest.mark.parametrize("name", [
    "firefox.pkg.tar.zst.1", "x.pkg", "x.tar.zst", "X.PKG.TAR.ZST",
    "a.deb", "", "pkg.tar.zst.tmp", "x.pkg.tar.zst.sig", "x.pkg.tar.gz.asc",
])
def test_arch_pkg_negatif(name):
    """ORTAM: eksik/yanlis/buyukharf sonek False ('.pkg.tar' tek basina gecerli!)."""
    assert _is_arch_pkg_name(name) is False


def test_arch_pkg_pkg_tar_kuyrugu_gecerli():
    """ORTAM-OGRENDI: '.pkg.tar' _ARCH_PKG_TAIL icinde — kisa kuyruk da True."""
    assert _is_arch_pkg_name("x.pkg.tar") is True


# == _classify_dir =================================================================================

@pytest.mark.parametrize("marker,system", _BUILD_MARKERS)
def test_classify_dir_build_sistemi(tmp_path, marker, system):
    """ORTAM: her build marker'i -> SOURCE_DIR 0.85 + sistem + actions."""
    d = tmp_path / "src"
    d.mkdir()
    (d / marker).write_text("")
    r = _classify_dir(d)
    assert isinstance(r, IntakeResult)
    assert r.file_type == FileType.SOURCE_DIR
    assert r.confidence == 0.85
    assert r.build_system == system
    assert r.actions == ["build", "install"]
    assert r.ambiguous is False
    assert system in r.reason


def test_classify_dir_bos(tmp_path):
    """ORTAM: bos klasor -> UNKNOWN 0.2 ambiguous."""
    d = tmp_path / "empty"
    d.mkdir()
    r = _classify_dir(d)
    assert r.file_type == FileType.UNKNOWN
    assert r.confidence == 0.2
    assert r.ambiguous is True
    assert r.build_system is None
    assert "build sistemi bulunamadi" in r.reason


def test_classify_dir_markersiz_dosyalar(tmp_path):
    """ORTAM: build marker yoksa UNKNOWN ambiguous."""
    d = tmp_path / "plain"
    d.mkdir()
    (d / "README.md").write_text("")
    (d / "main.c").write_text("")
    r = _classify_dir(d)
    assert r.file_type == FileType.UNKNOWN
    assert r.ambiguous is True


def test_classify_dir_marker_artik_dosyalarla(tmp_path):
    """ORTAM: marker + artik dosya -> yine SOURCE_DIR."""
    d = tmp_path / "mix"
    d.mkdir()
    (d / "README.md").write_text("")
    (d / "go.mod").write_text("")
    r = _classify_dir(d)
    assert r.file_type == FileType.SOURCE_DIR
    assert r.build_system == "go"


def test_classify_dir_alt_klasorler_tarayamaz(tmp_path):
    """ORTAM: sadece ust-seviye entry adlari okunur (recursive degil)."""
    d = tmp_path / "top"
    d.mkdir()
    sub = d / "nested"
    sub.mkdir()
    (sub / "Cargo.toml").write_text("")  # alt klasorde -> gorulmez
    r = _classify_dir(d)
    assert r.file_type == FileType.UNKNOWN
    assert r.ambiguous is True


def test_classify_dir_okunamadi(monkeypatch, tmp_path):
    """ORTAM: iterdir OSError -> UNKNOWN 0.0 + 'klasor okunamadi'."""
    d = tmp_path / "noperm"
    d.mkdir()

    def boom(self):
        raise PermissionError("yetki yok")

    monkeypatch.setattr(Path, "iterdir", boom)
    r = _classify_dir(d)
    assert r.file_type == FileType.UNKNOWN
    assert r.confidence == 0.0
    assert "klasor okunamadi" in r.reason
    assert "yetki yok" in r.reason


# == _classify_tarball =============================================================================

@pytest.mark.parametrize("marker,system", _BUILD_MARKERS)
def test_classify_tarball_kaynak(tmp_path, marker, system):
    """ORTAM: sadece build marker -> SOURCE_TARBALL 0.85."""
    p = _make_tar(tmp_path / "src.tar.gz", [f"proj/{marker}", "proj/main.c"])
    r = _classify_tarball(p)
    assert r.file_type == FileType.SOURCE_TARBALL
    assert r.confidence == 0.85
    assert r.build_system == system
    assert r.actions == ["build", "install"]
    assert r.ambiguous is False


@pytest.mark.parametrize("path", ["usr/bin/myapp", "./usr/bin/myapp", "opt/x/usr/bin/y"])
def test_classify_tarball_binary(tmp_path, path):
    """ORTAM: usr/bin yerlesimi -> BINARY_TARBALL 0.7."""
    p = _make_tar(tmp_path / "bin.tar.gz", [path])
    r = _classify_tarball(p)
    assert r.file_type == FileType.BINARY_TARBALL
    assert r.confidence == 0.7
    assert r.actions == ["wrap", "install"]
    assert r.build_system is None


def test_classify_tarball_desktop_binary(tmp_path):
    """ORTAM: .desktop dosyasi da binary yerlesimi sayilir."""
    p = _make_tar(tmp_path / "dt.tar.gz", ["app/org.app.desktop"])
    r = _classify_tarball(p)
    assert r.file_type == FileType.BINARY_TARBALL


def test_classify_tarball_kaynak_ve_binary_ambigu(tmp_path):
    """ORTAM: hem marker hem binary -> UNKNOWN 0.4 ambiguous + iki action."""
    p = _make_tar(tmp_path / "both.tar.gz", ["proj/Cargo.toml", "usr/bin/app"])
    r = _classify_tarball(p)
    assert r.file_type == FileType.UNKNOWN
    assert r.confidence == 0.4
    assert r.ambiguous is True
    assert r.build_system == "cargo"
    assert r.actions == ["build", "wrap"]


def test_classify_tarball_icerik_tanimlanamadi(tmp_path):
    """ORTAM: ne marker ne binary -> UNKNOWN 0.2 ambiguous."""
    p = _make_tar(tmp_path / "odd.tar.gz", ["proj/main.c", "proj/README"])
    r = _classify_tarball(p)
    assert r.file_type == FileType.UNKNOWN
    assert r.confidence == 0.2
    assert r.ambiguous is True
    assert "tanimlanamadi" in r.reason


def test_classify_tarball_pkginfo_arch_pkg(tmp_path):
    """ORTAM: .PKGINFO -> ARCH_PKG 0.9 + install."""
    p = _make_tar(tmp_path / "arch.pkg.tar.zst", [".PKGINFO", "usr/bin/x"])
    r = _classify_tarball(p)
    assert r.file_type == FileType.ARCH_PKG
    assert r.confidence == 0.9
    assert r.actions == ["install"]


def test_classify_tarball_pkginfo_alt_klasorde(tmp_path):
    """ORTAM: alt klasordeki .PKGINFO da (basename karsilastirmasi) ARCH_PKG."""
    p = _make_tar(tmp_path / "nested.pkg.tar.zst", ["pkg/sub/.PKGINFO"])
    r = _classify_tarball(p)
    assert r.file_type == FileType.ARCH_PKG


def test_classify_tarball_pkginfo_binary_oncelikli(tmp_path):
    """ORTAM: .PKGINFO + build marker -> ARCH_PKG (oncelik)."""
    p = _make_tar(tmp_path / "mix.pkg.tar.zst", [".PKGINFO", "Cargo.toml"])
    r = _classify_tarball(p)
    assert r.file_type == FileType.ARCH_PKG


def test_classify_tarball_brozuk_arsiv(tmp_path):
    """ORTAM: gecersiz baytlar -> UNKNOWN 0.0 'arsiv okunamadi'."""
    p = tmp_path / "bad.tar.gz"
    p.write_bytes(b"bu bir tar degil" * 4)
    r = _classify_tarball(p)
    assert r.file_type == FileType.UNKNOWN
    assert r.confidence == 0.0
    assert "arsiv okunamadi" in r.reason


def test_classify_tarball_bos_arsiv(tmp_path):
    """ORTAM: bos arsiv (girdi yok) -> UNKNOWN 0.2 ambiguous."""
    p = _make_tar(tmp_path / "empty.tar.gz", [])
    r = _classify_tarball(p)
    assert r.file_type == FileType.UNKNOWN
    assert r.ambiguous is True


@pytest.mark.parametrize("mode,suffix", [("w:gz", ".tar.gz"), ("w:xz", ".tar.xz"),
                                         ("w:bz2", ".tar.bz2"), ("w", ".tar")])
def test_classify_tarball_sikistirma_formatlari(tmp_path, mode, suffix):
    """ORTAM: gzip/xz/bz2/duz tar hepsi acilir."""
    p = _make_tar(tmp_path / ("k" + suffix), ["proj/CMakeLists.txt"], mode=mode)
    r = _classify_tarball(p)
    assert r.file_type == FileType.SOURCE_TARBALL
    assert r.build_system == "cmake"


# == _sanitize_name ================================================================================

@pytest.mark.parametrize("raw,expected", [
    ("MyApp", "myapp"),
    ("My App", "my-app"),
    ("my app!", "my-app"),
    ("  spaced  ", "spaced"),
    ("--dash--", "dash"),
    ("..dots..", "dots"),
    ("-.-", "paket"),
    ("", "paket"),
    ("!!!", "paket"),
    ("linux@2.0+beta-1", "linux@2.0+beta-1"),
    ("a_b c", "a_b-c"),
    ("Pkg.Name-1.0", "pkg.name-1.0"),
    ("türkçe_paket", "t-rk-e_paket"),
    ("$$$", "paket"),
])
def test_sanitize_name(raw, expected):
    """ORTAM: gecersiz -> -, kucuk-harf, leading/trailing -/. ayikla, bos -> 'paket'."""
    assert _sanitize_name(raw) == expected


def test_sanitize_name_always_lowercase():
    """ORTAM: buyuk harf kalmaz."""
    assert _sanitize_name("ABCDEF") == "abcdef"


def test_sanitize_name_izinli_karakterler():
    """ORTAM: [a-zA-Z0-9@._+-] koriunur."""
    kept = "a1@._+Z"
    assert _sanitize_name(kept) == kept.lower()


# == _source_build_commands ========================================================================

@pytest.mark.parametrize("system,makedep0,build_needle,install_needle", [
    ("cmake", "cmake", "cmake -B build", 'DESTDIR="$pkgdir" cmake --install build'),
    ("meson", "meson", "meson setup build", 'DESTDIR="$pkgdir" meson install'),
    ("cargo", "rust", "cargo build --release --locked", "target/release/main"),
    ("autotools", "gcc", "./configure --prefix=/usr", 'make DESTDIR="$pkgdir" install'),
    ("python", "python-build", "python -m build --wheel", "python -m installer"),
    ("node", "nodejs", "npm ci && npm run build", "usr/lib/$pkgname"),
    ("go", "go", "go build -o app", "usr/bin/app"),
])
def test_source_build_commands_sistemler(system, makedep0, build_needle, install_needle):
    """ORTAM: her build sistemi 3-demet (makedepends, build, install) dondurur."""
    makedeps, build, install = _source_build_commands(system)
    assert isinstance(makedeps, list)
    assert isinstance(build, str)
    assert isinstance(install, str)
    assert makedeps[0] == makedep0
    assert build_needle in build
    assert install_needle in install


def test_source_build_commands_cargo_binary_name():
    """ORTAM-OGRENDI: cargo binary_name sadece INSTALL'da; build sabit 'cargo build'."""
    _, build, install = _source_build_commands("cargo")
    assert build == "cargo build --release --locked"
    assert "target/release/main" in install
    assert "$pkgdir/usr/bin/main" in install


@pytest.mark.parametrize("bn", ["myapp", "tool", "x"])
def test_source_build_commands_cargo_ozel_binary(bn):
    """ORTAM: cargo + binary_name -> install komutunda ayni isim (build'de YOK)."""
    _, build, install = _source_build_commands("cargo", bn)
    assert build == "cargo build --release --locked"
    assert f"target/release/{bn}" in install
    assert f"$pkgdir/usr/bin/{bn}" in install


def test_source_build_commands_go_default_binary():
    """ORTAM: go binary_name verilmeyince 'app' olur."""
    _, build, install = _source_build_commands("go")
    assert "go build -o app" in build
    assert "$pkgdir/usr/bin/app" in install


@pytest.mark.parametrize("bn", ["srv", "daemon"])
def test_source_build_commands_go_ozel_binary(bn):
    """ORTAM: go + binary_name -> ayni isim."""
    _, build, install = _source_build_commands("go", bn)
    assert f"go build -o {bn}" in build
    assert f"$pkgdir/usr/bin/{bn}" in install


@pytest.mark.parametrize("unknown", ["unknown", "", "make2", "MAKE", None])
def test_source_build_commands_bilinmeyen_make(unknown):
    """ORTAM: bilinmeyen sistem -> duz make varsayilani."""
    makedeps, build, install = _source_build_commands(unknown)
    assert makedeps == ["gcc"]
    assert build == "make"
    assert install == 'make DESTDIR="$pkgdir" install'


def test_source_build_commands_demet_uzunlugu():
    """ORTAM: donus her zaman 3-demet."""
    for system in ["cmake", "meson", "cargo", "autotools", "python", "node", "go", "x"]:
        assert len(_source_build_commands(system)) == 3
