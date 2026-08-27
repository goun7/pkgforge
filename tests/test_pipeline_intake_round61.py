"""Tur-61 — pipeline universal intake rotasi (deb/rpm disi turler)."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication

import core.pipeline as PL
from core import intake
from core.pipeline import ConversionPipeline


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


def _tools(**kw):
    base = {"missing_required": [], "missing_optional": [], "debtap": "",
            "makepkg": "/usr/bin/makepkg"}
    base.update(kw)
    return NS(**base)


@pytest.fixture()
def pipe(qapp, monkeypatch):
    monkeypatch.setattr(PL, "discover_tools", lambda: _tools())
    p = ConversionPipeline()
    p._set_step = lambda s, st: None
    return p


def _make_tar(path: Path, entries: dict, fmt: str = "gz") -> Path:
    mode = {"gz": "w:gz", "xz": "w:xz"}[fmt]
    with tarfile.open(path, mode) as tf:
        for name, data in entries.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


def _ir(ft, path, **kw):
    return intake.IntakeResult(ft, path, 0.8, "test", **kw)


# ── _classify_input ─────────────────────────────────────────────
def test_classify_input_forced_valid(pipe, tmp_path):
    f = tmp_path / "x.tar.gz"
    f.write_bytes(b"y")
    pipe._forced_type = "source_tarball"
    ir = pipe._classify_input(f)
    assert ir.file_type == intake.FileType.SOURCE_TARBALL
    assert ir.reason == "kullanici secimi"


def test_classify_input_forced_invalid(pipe, tmp_path):
    f = tmp_path / "x.tar.gz"
    f.write_bytes(b"y")
    pipe._forced_type = "gecersiz"
    assert pipe._classify_input(f).file_type == intake.FileType.UNKNOWN


def test_classify_input_delegates(pipe, tmp_path):
    f = tmp_path / "p.deb"
    f.write_bytes(b"x")
    assert pipe._classify_input(f).file_type == intake.FileType.DEB


# ── _intake_metadata ────────────────────────────────────────────
def test_intake_metadata_strips_suffix(pipe, tmp_path):
    f = tmp_path / "foo-1.2.tar.gz"
    f.write_bytes(b"x")
    meta = pipe._intake_metadata(f, _ir(intake.FileType.SOURCE_TARBALL, f))
    assert meta.name == "foo"
    assert meta.version == "1.2"
    assert meta.arch_mapped == "x86_64"


def test_intake_metadata_appimage(pipe, tmp_path):
    f = tmp_path / "MyApp.AppImage"
    f.write_bytes(b"x")
    meta = pipe._intake_metadata(f, _ir(intake.FileType.APPIMAGE, f))
    assert meta.name == "myapp"
    assert meta.version == "0.0.1"


# ── _run_intake_route: erken donus dallari ──────────────────────
def test_route_unknown_ambiguous(pipe, tmp_path):
    f = tmp_path / "m.tar.gz"
    f.write_bytes(b"x")
    pipe._temp_dir = tmp_path
    pipe._run_intake_route(f, _ir(intake.FileType.UNKNOWN, f, ambiguous=True))
    assert "belirsiz" in pipe._result.message


def test_route_unknown_plain(pipe, tmp_path):
    f = tmp_path / "m.bin"
    f.write_bytes(b"x")
    pipe._temp_dir = tmp_path
    pipe._run_intake_route(f, _ir(intake.FileType.UNKNOWN, f))
    assert "Taninamayan" in pipe._result.message


def test_route_flatpakref(pipe, tmp_path):
    f = tmp_path / "a.flatpakref"
    f.write_bytes(b"x")
    pipe._temp_dir = tmp_path
    pipe._run_intake_route(f, _ir(intake.FileType.FLATPAKREF, f))
    assert "flatpak-export" in pipe._result.message


# ── _run_intake_route: iptal noktalari ──────────────────────────
def test_route_cancel_before_security(pipe, tmp_path):
    f = tmp_path / "c.tar.gz"
    f.write_bytes(b"x")
    pipe._temp_dir = tmp_path
    pipe._cancelled = True
    pipe._run_intake_route(f, _ir(intake.FileType.SOURCE_TARBALL, f))
    assert pipe._result.converted_pkg is None


def test_route_cancel_after_security(pipe, tmp_path):
    f = _make_tar(tmp_path / "s.tar.gz", {"a/CMakeLists.txt": b"x"})
    pipe._temp_dir = tmp_path

    def set_step(s, st):
        if s == PL.PipelineStep.SECURITY and st == "done":
            pipe._cancelled = True

    pipe._set_step = set_step
    pipe._run_intake_route(f, _ir(intake.FileType.SOURCE_TARBALL, f))
    assert pipe._result.converted_pkg is None


def test_route_cancel_after_analysis(pipe, tmp_path):
    f = _make_tar(tmp_path / "s.tar.gz", {"a/CMakeLists.txt": b"x"})
    pipe._temp_dir = tmp_path

    def set_step(s, st):
        if s == PL.PipelineStep.ANALYSIS and st == "done":
            pipe._cancelled = True

    pipe._set_step = set_step
    pipe._run_intake_route(f, _ir(intake.FileType.SOURCE_TARBALL, f))
    assert pipe._result.converted_pkg is None


def test_route_cancel_after_convert(pipe, tmp_path, monkeypatch):
    f = _make_tar(tmp_path / "s.tar.gz", {"a/CMakeLists.txt": b"x"})
    pipe._temp_dir = tmp_path

    def conv(*a):
        pipe._cancelled = True
        return tmp_path / "o.pkg.tar.zst"

    monkeypatch.setattr(pipe, "_intake_convert", conv)
    pipe._run_intake_route(f, _ir(intake.FileType.SOURCE_TARBALL, f))
    assert pipe._result.converted_pkg is None


# ── _run_intake_route: basari ve hata ───────────────────────────
def test_route_source_success(pipe, tmp_path, monkeypatch):
    f = _make_tar(tmp_path / "foo-1.0.tar.gz", {"foo-1.0/CMakeLists.txt": b"x"})
    pipe._temp_dir = tmp_path
    monkeypatch.setattr(pipe, "_intake_convert", lambda *a: tmp_path / "out.pkg.tar.zst")
    fin = []
    monkeypatch.setattr(pipe, "_finalize_pkg", lambda pkg, meta: fin.append(pkg))
    pipe._run_intake_route(f, _ir(intake.FileType.SOURCE_TARBALL, f))
    assert fin and pipe._result.converted_pkg is not None


def test_route_convert_error(pipe, tmp_path, monkeypatch):
    f = _make_tar(tmp_path / "foo.tar.gz", {"foo/CMakeLists.txt": b"x"})
    pipe._temp_dir = tmp_path

    def boom(*a):
        raise RuntimeError("derleme patladi")

    monkeypatch.setattr(pipe, "_intake_convert", boom)
    pipe._run_intake_route(f, _ir(intake.FileType.SOURCE_TARBALL, f))
    assert "derleme patladi" in pipe._result.message


def test_route_arch_pkg(pipe, tmp_path, monkeypatch):
    f = tmp_path / "foo-1.0-1-x86_64.pkg.tar.zst"
    f.write_bytes(b"pkgdata")
    pipe._temp_dir = tmp_path / "temp"
    pipe._temp_dir.mkdir()
    calls = []
    monkeypatch.setattr(pipe, "_finalize_pkg", lambda pkg, meta: calls.append(pkg))
    pipe._run_intake_route(f, _ir(intake.FileType.ARCH_PKG, f))
    assert len(calls) == 1 and calls[0].name == f.name


# ── _intake_convert dispatch ────────────────────────────────────
def test_convert_dispatch(pipe, tmp_path, monkeypatch):
    f = tmp_path / "x"
    f.write_bytes(b"x")
    meta = NS(name="x", version="1")
    pipe._temp_dir = tmp_path / "temp"
    pipe._temp_dir.mkdir()

    out = pipe._intake_convert(f, _ir(intake.FileType.ARCH_PKG, f), meta)
    assert out.name == "x"

    monkeypatch.setattr(pipe, "_build_from_source_dir", lambda *a: Path("sd"))
    assert pipe._intake_convert(f, _ir(intake.FileType.SOURCE_DIR, f), meta) == Path("sd")

    monkeypatch.setattr(pipe, "_build_from_source_tarball", lambda *a: Path("st"))
    assert pipe._intake_convert(f, _ir(intake.FileType.SOURCE_TARBALL, f), meta) == Path("st")

    monkeypatch.setattr(pipe, "_wrap_binary", lambda *a: Path("wb"))
    assert pipe._intake_convert(f, _ir(intake.FileType.BINARY_TARBALL, f), meta) == Path("wb")

    with pytest.raises(RuntimeError):
        pipe._intake_convert(f, _ir(intake.FileType.FLATPAKREF, f), meta)


# ── _run_makepkg ────────────────────────────────────────────────
def test_makepkg_no_tool(pipe, tmp_path):
    pipe._tools = _tools(makepkg="")
    with pytest.raises(RuntimeError, match="makepkg bulunamadi"):
        pipe._run_makepkg(tmp_path)


def test_makepkg_success(pipe, tmp_path, monkeypatch):
    (tmp_path / "foo-1.0-1-x86_64.pkg.tar.zst").write_bytes(b"pkg")
    monkeypatch.setattr("core.security.safe_run",
                        lambda *a, **k: NS(returncode=0, stdout="ok", stderr=""))
    assert pipe._run_makepkg(tmp_path).name.endswith(".pkg.tar.zst")


def test_makepkg_failure(pipe, tmp_path, monkeypatch):
    monkeypatch.setattr("core.security.safe_run",
                        lambda *a, **k: NS(returncode=1, stdout="", stderr="hata"))
    with pytest.raises(RuntimeError, match="makepkg basarisiz"):
        pipe._run_makepkg(tmp_path)


def test_makepkg_no_output(pipe, tmp_path, monkeypatch):
    monkeypatch.setattr("core.security.safe_run",
                        lambda *a, **k: NS(returncode=0, stdout="", stderr=""))
    with pytest.raises(RuntimeError, match="paket dosyasi bulunamadi"):
        pipe._run_makepkg(tmp_path)


# ── _extract_tarball ────────────────────────────────────────────
def test_extract_tarball(pipe, tmp_path):
    f = _make_tar(tmp_path / "a.tar.gz", {"a-1/hello.txt": b"hi"})
    dest = tmp_path / "out"
    dest.mkdir()
    pipe._extract_tarball(f, dest)
    assert (dest / "a-1" / "hello.txt").exists()


# ── _build_from_source_tarball ──────────────────────────────────
def test_build_source_tarball(pipe, tmp_path, monkeypatch):
    f = _make_tar(tmp_path / "foo-1.0.tar.gz",
                  {"foo-1.0/CMakeLists.txt": b"project(foo VERSION 1.0)"})
    pipe._temp_dir = tmp_path / "temp"
    pipe._temp_dir.mkdir()
    meta = NS(name="foo", version="1.0")
    monkeypatch.setattr(pipe, "_run_makepkg", lambda bd: bd / "out.pkg.tar.zst")
    out = pipe._build_from_source_tarball(f, _ir(intake.FileType.SOURCE_TARBALL, f,
                                                 build_system="cmake"), meta)
    assert out.name == "out.pkg.tar.zst"
    pkgbuild = (pipe._temp_dir / "build_src" / "PKGBUILD").read_text()
    assert "pkgname=foo" in pkgbuild and "cmake -B build" in pkgbuild


# ── _build_from_source_dir ──────────────────────────────────────
def test_build_source_dir(pipe, tmp_path, monkeypatch):
    src = tmp_path / "mysrc"
    src.mkdir()
    (src / "CMakeLists.txt").write_text("project(x)")
    pipe._temp_dir = tmp_path / "temp"
    pipe._temp_dir.mkdir()
    meta = NS(name="mysrc", version="1.0")
    captured = {}

    def fake_tb(tb, sub_ir, m):
        captured["tarball"] = tb
        return Path("built.pkg.tar.zst")

    monkeypatch.setattr(pipe, "_build_from_source_tarball", fake_tb)
    out = pipe._build_from_source_dir(src, _ir(intake.FileType.SOURCE_DIR, src,
                                               build_system="cmake"), meta)
    assert out == Path("built.pkg.tar.zst")
    assert captured["tarball"].name == "mysrc.tar.gz"


# ── _wrap_binary ────────────────────────────────────────────────
def test_wrap_binary_tarball(pipe, tmp_path, monkeypatch):
    f = _make_tar(tmp_path / "app-1.0.tar.gz", {"usr/bin/app": b"ELF"})
    pipe._temp_dir = tmp_path / "temp"
    pipe._temp_dir.mkdir()
    meta = NS(name="app", version="1.0")
    monkeypatch.setattr(pipe, "_run_makepkg", lambda bd: bd / "w.pkg.tar.zst")
    out = pipe._wrap_binary(f, _ir(intake.FileType.BINARY_TARBALL, f), meta)
    assert out.name == "w.pkg.tar.zst"
    pkgbuild = (pipe._temp_dir / "build_bin" / "PKGBUILD").read_text()
    assert "pkgname=app" in pkgbuild and "ln -sf" in pkgbuild


def test_wrap_binary_appimage(pipe, tmp_path, monkeypatch):
    f = tmp_path / "app.AppImage"
    f.write_bytes(b"ELF")
    pipe._temp_dir = tmp_path / "temp"
    pipe._temp_dir.mkdir()
    meta = NS(name="app", version="1.0")
    fake_tar = tmp_path / "ext.tar.gz"
    monkeypatch.setattr(pipe, "_extract_appimage",
                        lambda p: _make_tar(fake_tar, {"usr/bin/app": b"ELF"}))
    monkeypatch.setattr(pipe, "_run_makepkg", lambda bd: bd / "a.pkg.tar.zst")
    out = pipe._wrap_binary(f, _ir(intake.FileType.APPIMAGE, f), meta)
    assert out.name == "a.pkg.tar.zst"


# ── _extract_appimage ───────────────────────────────────────────
def test_extract_appimage_fails(pipe, tmp_path, monkeypatch):
    f = tmp_path / "app.AppImage"
    f.write_bytes(b"ELF")
    pipe._temp_dir = tmp_path / "temp"
    pipe._temp_dir.mkdir()
    monkeypatch.setattr("core.security.safe_run",
                        lambda *a, **k: NS(returncode=1, stdout="", stderr="e"))
    with pytest.raises(RuntimeError, match="AppImage acilamadi"):
        pipe._extract_appimage(f)


def test_extract_appimage_no_root(pipe, tmp_path, monkeypatch):
    f = tmp_path / "app.AppImage"
    f.write_bytes(b"ELF")
    pipe._temp_dir = tmp_path / "temp"
    pipe._temp_dir.mkdir()
    monkeypatch.setattr("core.security.safe_run",
                        lambda *a, **k: NS(returncode=0, stdout="", stderr=""))
    with pytest.raises(RuntimeError, match="squashfs-root bulunamadi"):
        pipe._extract_appimage(f)


def test_extract_appimage_success(pipe, tmp_path, monkeypatch):
    f = tmp_path / "app.AppImage"
    f.write_bytes(b"ELF")
    pipe._temp_dir = tmp_path / "temp"
    pipe._temp_dir.mkdir()

    def fake_run(cmd, **kw):
        root = Path(kw["cwd"]) / "squashfs-root"
        (root / "usr" / "bin").mkdir(parents=True)
        (root / "usr" / "bin" / "app").write_bytes(b"ELF")
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("core.security.safe_run", fake_run)
    out = pipe._extract_appimage(f)
    assert out.name == "app.tar.gz"


# ── kalan dallar: forced run, boyut uyarisi, build-sistemi fallback ──
def test_run_with_forced_type(pipe, tmp_path, monkeypatch):
    f = tmp_path / "x.tar.gz"
    f.write_bytes(b"x")
    monkeypatch.setattr(pipe, "_run_pipeline", lambda p: None)
    monkeypatch.setattr(pipe, "_record_history", lambda p: None)
    monkeypatch.setattr(pipe, "_cleanup", lambda: None)
    pipe.run(f, "source_tarball")
    assert pipe._forced_type == "source_tarball"


def test_route_size_warning(pipe, tmp_path, monkeypatch):
    f = _make_tar(tmp_path / "s.tar.gz", {"a/CMakeLists.txt": b"x"})
    pipe._temp_dir = tmp_path
    monkeypatch.setattr(PL, "validate_file_size", lambda *a, **k: "cok buyuk")
    monkeypatch.setattr(pipe, "_intake_convert", lambda *a: tmp_path / "o.pkg.tar.zst")
    monkeypatch.setattr(pipe, "_finalize_pkg", lambda pkg, meta: None)
    pipe._run_intake_route(f, _ir(intake.FileType.SOURCE_TARBALL, f))
    assert pipe._result.size_warning == "cok buyuk"


def test_build_source_dir_buildsys_fallback(pipe, tmp_path, monkeypatch):
    src = tmp_path / "mysrc"
    src.mkdir()
    (src / "readme.txt").write_text("x")  # build belirteci yok
    pipe._temp_dir = tmp_path / "temp"
    pipe._temp_dir.mkdir()
    meta = NS(name="mysrc", version="1.0")
    ir = intake.IntakeResult(intake.FileType.SOURCE_DIR, src, 0.85, "",
                             build_system="cmake")
    captured = {}

    def fake_tb(tb, sub_ir, m):
        captured["build_system"] = sub_ir.build_system
        return Path("b.pkg.tar.zst")

    monkeypatch.setattr(pipe, "_build_from_source_tarball", fake_tb)
    out = pipe._build_from_source_dir(src, ir, meta)
    assert out == Path("b.pkg.tar.zst")
    assert captured["build_system"] == "cmake"
