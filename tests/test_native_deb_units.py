"""Coverage itmesi — core/native_deb_converter.py donusum akisi."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication

import core.native_deb_converter as ND
from core.native_deb_converter import (
    NativeDebConverter,
    _sanitize_pkgname,
    _sanitize_version,
)
from core.package_analyzer import PackageMetadata


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class Hook:
    def __init__(self):
        self.fns = []

    def connect(self, fn):
        self.fns.append(fn)


class FakeQProcess:
    ProcessChannelMode = NS(MergedChannels=3)
    last = None

    def __init__(self, parent=None):
        self.started = []
        self.env = {}
        self.readyReadStandardOutput = Hook()
        self.finished = Hook()
        self.errorOccurred = Hook()
        self.workdir = ""
        FakeQProcess.last = self

    def setWorkingDirectory(self, d):
        self.workdir = d

    def setProcessChannelMode(self, m):
        pass

    def setProcessEnvironment(self, env):
        self.env_obj = env

    def start(self, prog, args):
        self.started.append((prog, args))


def test_sanitize_pkgname_matrix():
    assert _sanitize_pkgname("My App") == "my-app"
    assert _sanitize_pkgname("  LIB.net+X ") == "lib.net+x"
    assert _sanitize_pkgname("!!!") == "---"


def test_sanitize_version_matrix():
    assert _sanitize_version("2:1.0-3") == "1.0"
    assert _sanitize_version("9.9~rc1") == "9.9~rc1"
    assert _sanitize_version("") == "1.0.0"


def _meta():
    return PackageMetadata(
        name="TestPkg", version="2:3.1-4", arch_mapped="x86_64",
        description="Kisa aciklama", url="https://ornek.test")


def test_generate_pkgbuild(qapp):
    conv = NativeDebConverter(NS(makepkg="", ar="", bsdtar=""))
    pb = conv._generate_pkgbuild(_meta(), ["curl", "git"])
    assert "pkgname=" in pb and "testpkg" in pb
    assert "pkgver=" in pb and "3.1" in pb
    assert "depends=(" in pb and "curl" in pb and "git" in pb
    assert "x86_64" in pb

    pb2 = conv._generate_pkgbuild(_meta(), None)
    assert "depends=()" in pb2


def test_find_output_package_skips_sidecars(qapp, tmp_path):
    conv = NativeDebConverter(NS(makepkg="", ar="", bsdtar=""))
    conv._work_dir = tmp_path
    out = tmp_path / "native_build" / "pkgout"
    out.mkdir(parents=True)
    (out / "p.pkg.tar.zst.sig").write_bytes(b"s")
    gercek = out / "p-1-1-x86_64.pkg.tar.zst"
    gercek.write_bytes(b"p")
    assert conv._find_output_package() == gercek


def test_convert_guards(qapp, tmp_path):
    tools = NS(makepkg="/usr/bin/makepkg", ar="/usr/bin/ar", bsdtar="bsdtar")
    conv = NativeDebConverter(tools)
    got = []
    conv.finished.connect(lambda ok, msg, p: got.append((ok, msg, p)))
    conv.convert(tmp_path / "yok.deb", tmp_path)
    assert got[0][0] is False and "bulunamadı" in got[0][1]

    f = tmp_path / "x.deb"
    f.write_bytes(b"d")
    conv2 = NativeDebConverter(NS(makepkg="", ar="", bsdtar=""))
    got2 = []
    conv2.finished.connect(lambda ok, msg, p: got2.append((ok, msg, p)))
    conv2.convert(f, tmp_path)
    assert got2[0][0] is False and "makepkg bulunamadı" in got2[0][1]


def test_cancel_sets_flag(qapp):
    conv = NativeDebConverter(NS(makepkg="", ar="", bsdtar=""))
    conv.cancel()
    assert conv._cancelled is True


def test_convert_happy_path(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ND, "QProcess", FakeQProcess)
    tools = NS(makepkg="/usr/bin/makepkg", ar="/usr/bin/ar",
               bsdtar="bsdtar", bwrap="", pkexec="")
    deb = tmp_path / "ara.deb"
    deb.write_bytes(b"DEB")
    out_dir = tmp_path / "cikti"
    out_dir.mkdir()

    monkeypatch.setattr(ND, "analyze_package", lambda p, t: _meta())
    monkeypatch.setattr(NativeDebConverter, "_extract_data_tar",
                        lambda self, dp, dest: None)
    monkeypatch.setattr(ND, "resolve_runtime_dependencies",
                        lambda s, t: ["curl"])

    conv = NativeDebConverter(tools)
    got = []
    conv.finished.connect(lambda ok, msg, p: got.append((ok, msg, p)))
    conv.convert(deb, out_dir)

    proc = FakeQProcess.last
    assert proc is not None and len(proc.started) == 1
    assert "makepkg" in proc.started[0][0]
    pb = out_dir / "native_build" / "PKGBUILD"
    assert pb.is_file() and "testpkg" in pb.read_text()

    pkgout = out_dir / "native_build" / "pkgout"
    (pkgout / "testpkg-3.1-1-x86_64.pkg.tar.zst").write_bytes(b"P")
    conv._on_makepkg_finished(0, None)
    assert got[-1][0] is True
    assert got[-1][2].name == "testpkg-3.1-1-x86_64.pkg.tar.zst"
