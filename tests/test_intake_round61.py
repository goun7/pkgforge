"""Tur-61 — Evrensel girdi katmani: classify, tarball sezgisi, binary PKGBUILD."""
from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

from core.intake import (
    FileType,
    _list_archive,
    _read_magic,
    classify,
    derive_name_version,
    detect_build_system,
    find_binary_entrypoint,
    find_top_level_dir,
    generate_binary_pkgbuild,
    generate_source_tarball_pkgbuild,
    looks_like_binary_layout,
)


# ── Yardimcilar ─────────────────────────────────────────────────
def _make_tar(path: Path, entries: dict, fmt: str = "gz") -> Path:
    mode = {"gz": "w:gz", "xz": "w:xz", "bz2": "w:bz2"}[fmt]
    with tarfile.open(str(path), mode) as tf:  # type: ignore[call-overload]
        for name, data in entries.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


def _make_zip(path: Path, entries: dict) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


# ── Sonek bazli siniflandirma ───────────────────────────────────
def test_classify_deb_suffix(tmp_path):
    f = tmp_path / "paket.deb"
    f.write_bytes(b"whatever")
    r = classify(f)
    assert r.file_type == FileType.DEB
    assert "convert" in r.actions and "install" in r.actions


def test_classify_rpm_suffix(tmp_path):
    f = tmp_path / "paket.rpm"
    f.write_bytes(b"whatever")
    assert classify(f).file_type == FileType.RPM


def test_classify_appimage_suffix(tmp_path):
    f = tmp_path / "app.AppImage"
    f.write_bytes(b"x")
    assert classify(f).file_type == FileType.APPIMAGE


def test_classify_flatpakref_suffix(tmp_path):
    f = tmp_path / "org.foo.App.flatpakref"
    f.write_bytes(b"x")
    assert classify(f).file_type == FileType.FLATPAKREF


def test_classify_arch_pkg_suffix(tmp_path):
    f = tmp_path / "foo-1.0-1-x86_64.pkg.tar.zst"
    f.write_bytes(b"x")
    r = classify(f)
    assert r.file_type == FileType.ARCH_PKG
    assert r.actions == ["install"]


# ── Magic-bytes bazli ───────────────────────────────────────────
def test_classify_deb_magic_no_ext(tmp_path):
    f = tmp_path / "paket"
    f.write_bytes(b"!<arch>" + b"0" * 32)
    r = classify(f)
    assert r.file_type == FileType.DEB
    assert "magic" in r.reason


def test_classify_rpm_magic_no_ext(tmp_path):
    f = tmp_path / "paket"
    f.write_bytes(bytes.fromhex("edabeedb") + b"0" * 32)
    assert classify(f).file_type == FileType.RPM


# ── Tarball icerik sezgisi ──────────────────────────────────────
def test_classify_source_tarball_cargo(tmp_path):
    f = _make_tar(tmp_path / "app.tar.gz", {"app-1.0/Cargo.toml": b"[package]"})
    r = classify(f)
    assert r.file_type == FileType.SOURCE_TARBALL
    assert r.build_system == "cargo"
    assert not r.ambiguous


def test_classify_source_tarball_cmake_xz(tmp_path):
    f = _make_tar(tmp_path / "app.tar.xz", {"app/CMakeLists.txt": b"project(x)"}, fmt="xz")
    r = classify(f)
    assert r.file_type == FileType.SOURCE_TARBALL
    assert r.build_system == "cmake"


def test_classify_binary_tarball_usrbin(tmp_path):
    f = _make_tar(tmp_path / "bin.tar.gz", {"usr/bin/myapp": b"ELF"})
    r = classify(f)
    assert r.file_type == FileType.BINARY_TARBALL
    assert "wrap" in r.actions


def test_classify_binary_tarball_desktop(tmp_path):
    f = _make_tar(tmp_path / "bin.tar.gz",
                  {"share/applications/foo.desktop": b"[Desktop Entry]"})
    assert classify(f).file_type == FileType.BINARY_TARBALL


def test_classify_tarball_pkginfo(tmp_path):
    f = _make_tar(tmp_path / "arch.tar.gz", {".PKGINFO": b"pkgname = foo"})
    assert classify(f).file_type == FileType.ARCH_PKG


def test_classify_tarball_ambiguous_both(tmp_path):
    f = _make_tar(tmp_path / "mix.tar.gz",
                  {"Cargo.toml": b"[package]", "usr/bin/app": b"ELF"})
    r = classify(f)
    assert r.file_type == FileType.UNKNOWN
    assert r.ambiguous is True
    assert r.build_system == "cargo"


def test_classify_tarball_unknown_neither(tmp_path):
    f = _make_tar(tmp_path / "veri.tar.gz", {"README.md": b"hi"})
    r = classify(f)
    assert r.file_type == FileType.UNKNOWN
    assert r.ambiguous is True


def test_classify_corrupt_tarball(tmp_path):
    f = tmp_path / "bozuk.tar.gz"
    f.write_bytes(b"bu bir arsiv degil")
    r = classify(f)
    assert r.file_type == FileType.UNKNOWN
    assert "okunamadi" in r.reason


def test_classify_zip_source(tmp_path):
    f = _make_zip(tmp_path / "kod.zip", {"setup.py": b"from setuptools import setup"})
    r = classify(f)
    assert r.file_type == FileType.SOURCE_TARBALL
    assert r.build_system == "python"


# ── Magic ile uzantisiz tarball ─────────────────────────────────
def test_classify_gz_magic_no_suffix(tmp_path):
    f = _make_tar(tmp_path / "foo.bin", {"Cargo.toml": b"x"}, fmt="gz")
    r = classify(f)
    assert r.file_type == FileType.SOURCE_TARBALL


def test_classify_zip_magic_no_suffix(tmp_path):
    f = _make_zip(tmp_path / "foo.xyz", {"setup.py": b"x"})
    assert classify(f).file_type == FileType.SOURCE_TARBALL


def test_classify_bz2_magic_no_suffix(tmp_path):
    f = _make_tar(tmp_path / "foo.xyz", {"Makefile": b"all:"}, fmt="bz2")
    r = classify(f)
    assert r.file_type == FileType.SOURCE_TARBALL
    assert r.build_system == "make"


def test_classify_xz_magic_no_suffix(tmp_path):
    f = _make_tar(tmp_path / "foo.xyz", {"meson.build": b"project('x')"}, fmt="xz")
    r = classify(f)
    assert r.file_type == FileType.SOURCE_TARBALL
    assert r.build_system == "meson"


def test_classify_zst_suffix_unreadable(tmp_path):
    f = tmp_path / "foo.tar.zst"
    f.write_bytes(bytes.fromhex("28b52ffd") + b"cop")
    r = classify(f)
    assert r.file_type == FileType.UNKNOWN
    assert "okunamadi" in r.reason


# ── Klasor siniflandirma ────────────────────────────────────────
def test_classify_dir_source(tmp_path):
    d = tmp_path / "kaynak"
    d.mkdir()
    (d / "meson.build").write_text("project('x')")
    r = classify(d)
    assert r.file_type == FileType.SOURCE_DIR
    assert r.build_system == "meson"


def test_classify_dir_no_marker(tmp_path):
    d = tmp_path / "bos"
    d.mkdir()
    r = classify(d)
    assert r.file_type == FileType.UNKNOWN
    assert r.ambiguous is True


def test_classify_dir_oserror(tmp_path, monkeypatch):
    d = tmp_path / "kilitli"
    d.mkdir()

    def _patlat(self):
        raise OSError("izin yok")

    monkeypatch.setattr(Path, "iterdir", _patlat)
    r = classify(d)
    assert r.file_type == FileType.UNKNOWN
    assert "okunamadi" in r.reason


def test_classify_missing_path(tmp_path):
    r = classify(tmp_path / "yok.deb")
    assert r.file_type == FileType.UNKNOWN
    assert r.confidence == 0.0


def test_classify_unknown_file(tmp_path):
    f = tmp_path / "not.txt"
    f.write_text("merhaba")
    r = classify(f)
    assert r.file_type == FileType.UNKNOWN
    assert "tanimanamayan" in r.reason


# ── Yardimci islevler ───────────────────────────────────────────
def test_read_magic_oserror(tmp_path):
    d = tmp_path / "klasor"
    d.mkdir()
    assert _read_magic(d) == b""


def test_list_archive_bad_zip(tmp_path):
    f = tmp_path / "bozuk.zip"
    f.write_bytes(b"zip degil")
    assert _list_archive(f) is None


def test_detect_build_system_priority():
    names = ["a/Makefile", "a/Cargo.toml"]
    assert detect_build_system(names) == "cargo"


def test_detect_build_system_none():
    assert detect_build_system(["README"]) is None


def test_looks_binary_false():
    assert looks_like_binary_layout(["README", "src/main.c"]) is False


def test_find_entrypoint_found():
    names = ["a/usr/bin/foo", "a/usr/share/x"]
    assert find_binary_entrypoint(names) == "usr/bin/foo"


def test_find_entrypoint_none():
    assert find_binary_entrypoint(["README"]) is None


# ── Binary PKGBUILD uretimi ─────────────────────────────────────
def test_generate_pkgbuild_basic():
    out = generate_binary_pkgbuild("myapp", "1.2.3", "myapp.tar.gz")
    assert "pkgname=myapp" in out
    assert "pkgver=1.2.3" in out
    assert 'source=("myapp.tar.gz")' in out
    assert 'sha256sums=("SKIP")' in out
    assert "package() {" in out
    assert "/opt/myapp" in out
    assert "ln -sf" not in out
    assert "PkgForge ile sarildi" in out


def test_generate_pkgbuild_with_exec():
    out = generate_binary_pkgbuild("myapp", "1.0", "m.tgz",
                                   exec_relpath="usr/bin/myapp")
    assert 'install -d "$pkgdir/usr/bin"' in out
    # A4: wrapper script launches the app from /opt/<name>/<exec_relpath>
    assert 'exec /opt/myapp/usr/bin/myapp "$@"' in out
    assert 'chmod +x "$pkgdir/usr/bin/myapp"' in out
    # A4: .desktop file registers the app in the application menu
    assert '[Desktop Entry]' in out
    assert 'Name=myapp' in out
    assert 'Exec=myapp' in out


def test_generate_pkgbuild_desc_quotes():
    out = generate_binary_pkgbuild("a", "1", "a.tgz", description='Iyi "app"')
    assert 'pkgdesc="Iyi app"' in out


# ── Kaynak tarball PKGBUILD ─────────────────────────────────────
def test_find_top_level_dir_found():
    assert find_top_level_dir(["a-1/src", "a-1/README"]) == "a-1"


def test_find_top_level_dir_scattered():
    assert find_top_level_dir(["a/x", "b/y"]) is None


def test_find_top_level_dir_root_files():
    assert find_top_level_dir(["README", "Makefile"]) is None


def test_generate_source_pkgbuild_cmake():
    out = generate_source_tarball_pkgbuild(
        "foo", "1.0", "foo-1.0.tar.gz", "foo-1.0", "cmake",
        license_id="MIT", description="Bir arac")
    assert "pkgname=foo" in out
    assert "pkgver=1.0" in out
    assert 'source=("foo-1.0.tar.gz")' in out
    assert 'cd "$srcdir/foo-1.0"' in out
    assert "cmake -B build" in out
    assert "license=('MIT')" in out
    assert "makedepends=('cmake' 'gcc')" in out


def test_generate_source_pkgbuild_cargo_binary():
    out = generate_source_tarball_pkgbuild(
        "bar", "2.0", "bar.tar.gz", None, "cargo", binary_name="barbin")
    assert 'cd "$srcdir"' in out
    assert "cargo build --release --locked" in out
    assert 'install -Dm755 target/release/barbin "$pkgdir/usr/bin/barbin"' in out


def test_generate_source_pkgbuild_systems():
    for sysname, marker in [
        ("meson", "meson setup build"),
        ("autotools", "./configure"),
        ("python", "python -m build"),
        ("node", "npm ci"),
        ("go", "go build"),
        ("make", "make"),
    ]:
        out = generate_source_tarball_pkgbuild("p", "1", "p.tgz", "p-1", sysname)
        assert marker in out, sysname


def test_generate_source_pkgbuild_default_desc():
    out = generate_source_tarball_pkgbuild("q", "1", "q.tgz", "q-1", "cmake")
    assert "PkgForge kaynak derleme" in out


# ── Isim/versiyon turetme ───────────────────────────────────────
def test_derive_name_version_basic():
    assert derive_name_version("foo-1.0") == ("foo", "1.0")


def test_derive_name_version_vprefix():
    assert derive_name_version("node-v20.11.0-linux-x64") == ("node", "20.11.0")


def test_derive_name_version_noversion():
    name, ver = derive_name_version("SomeApp_Linux")
    assert ver == "0.0.1"
    assert name == "someapp_linux"


def test_derive_name_version_archpkg():
    assert derive_name_version("foo-1.0-1-x86_64.pkg.tar") == ("foo", "1.0")


def test_derive_name_version_noleadsep():
    # Basinda -/_ olmadigindan versiyon eslesmez, govde isim olur.
    name, ver = derive_name_version("1.2.3")
    assert name == "1.2.3"
    assert ver == "0.0.1"