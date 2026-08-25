"""Tur-28 — native_deb_converter Qt isleyici ve guvenlik dallari."""
from __future__ import annotations

import subprocess
from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication

import core.native_deb_converter as ND
from core.native_deb_converter import NativeDebConverter


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class Hook:
    def __init__(self):
        self.fns = []

    def connect(self, fn):
        self.fns.append(fn)

    def emit(self, *a):
        for fn in list(self.fns):
            fn(*a)


def _donusturucu():
    nd = NativeDebConverter.__new__(NativeDebConverter)
    ND.QObject.__init__(nd)
    nd._tools = NS(ar="/usr/bin/ar", bsdtar="/usr/bin/bsdtar",
               makepkg="/usr/bin/makepkg")
    nd._work_dir = None
    nd._process = None
    nd._cancelled = False
    nd.finished = Hook()
    nd.output_line = Hook()
    nd.sonuc = []
    nd.finished.connect(lambda ok, msg, pkg: nd.sonuc.append((ok, msg, pkg)))
    return nd


def _meta():
    return NS(name="demo", version="1.0", arch="amd64",
              arch_mapped="x86_64", package_type="deb",
              file_list=[], summary="ozet", description="aciklama",
              license="MIT", url="https://ornek")


def test_analyze_failure_emits_finished(qapp, monkeypatch, tmp_path):
    nd = _donusturucu()

    def patla(p, t):
        raise ValueError("analiz kirik")
    monkeypatch.setattr(ND, "analyze_package", patla)
    girdi = tmp_path / "girdi.deb"
    girdi.write_bytes(b"D")
    nd.convert(girdi, tmp_path)
    assert nd.sonuc and nd.sonuc[0][0] is False
    assert "analizi başarısız" in nd.sonuc[0][1]


def _hazirla_extract(monkeypatch, tmp_path):
    deb = tmp_path / "girdi.deb"
    deb.write_bytes(b"D")
    monkeypatch.setattr(ND, "analyze_package", lambda p, t: _meta())
    monkeypatch.setattr(NativeDebConverter, "_extract_data_tar",
                        lambda self, dp, dd: None)
    monkeypatch.setattr(ND, "check_symlink_attacks", lambda d: [])
    monkeypatch.setattr(ND, "check_dangerous_files",
                        lambda d: ([], []))
    monkeypatch.setattr("core.dep_resolver.resolve_runtime_dependencies",
                        lambda d, t: ["kit1", "kit2"])
    monkeypatch.setattr(NativeDebConverter, "_run_makepkg", lambda s, b: None)
    return deb


def test_security_escape_rejected(qapp, monkeypatch, tmp_path):
    nd = _donusturucu()
    deb = _hazirla_extract(monkeypatch, tmp_path)
    monkeypatch.setattr(ND, "check_symlink_attacks",
                        lambda d: ["/disari/evul"])
    nd.convert(deb, tmp_path)
    assert nd.sonuc[0][0] is False and "Güvenlik" in nd.sonuc[0][1]


def test_dangerous_errors_rejected(qapp, monkeypatch, tmp_path):
    nd = _donusturucu()
    deb = _hazirla_extract(monkeypatch, tmp_path)
    monkeypatch.setattr(ND, "check_dangerous_files",
                        lambda d: (["setuid yasak"], []))
    nd.convert(deb, tmp_path)
    assert nd.sonuc[0][0] is False and "tehlikeli" in nd.sonuc[0][1]


def test_warnings_emitted_and_flow_continues(qapp, monkeypatch, tmp_path):
    nd = _donusturucu()
    deb = _hazirla_extract(monkeypatch, tmp_path)
    monkeypatch.setattr(ND, "check_dangerous_files",
                        lambda d: ([], ["uyari-setuid"]))
    nd.convert(deb, tmp_path)
    # akis sonuna kadar gittigi icin hata mesaji YOK:
    assert all(not s[1].startswith("Dönüşüm hatası") for s in nd.sonuc)


def test_extract_data_tar_success_and_failures(monkeypatch, tmp_path):
    nd = _donusturucu()
    deb = tmp_path / "x.deb"
    deb.write_bytes(b"D")

    monkeypatch.setattr(ND, "safe_run",
                        lambda *a, **k: NS(returncode=1, stderr="ar yok"))
    with pytest.raises(RuntimeError, match="ar başarısız"):
        nd._extract_data_tar(deb, tmp_path)

    monkeypatch.setattr(ND, "safe_run",
                        lambda *a, **k: NS(returncode=0, stdout="control.tar.gz\n"))
    with pytest.raises(RuntimeError, match="data.tar bulunamadı"):
        nd._extract_data_tar(deb, tmp_path)

    # basarili zincir: ar p + tar -xf
    monkeypatch.setattr(ND, "safe_run",
                        lambda *a, **k: NS(returncode=0, stdout="data.tar.xz\n"))

    class SahteSurec:
        def __init__(self, rc=0):
            self.stdout = NS(close=lambda: None)
            self.stderr = NS(read=lambda: b"")
            self.returncode = rc

        def wait(self, timeout=0):
            return 0

        def communicate(self, timeout=0):
            return (b"", b"")

    def sahte_popen(cmd, *a, **k):
        if cmd[:2] == [str(nd._tools.ar), "p"]:
            return SahteSurec(0)
        return SahteSurec(0)

    monkeypatch.setattr(subprocess, "Popen", sahte_popen)
    nd._extract_data_tar(deb, tmp_path)      # istisna firlatmamali


def test_on_output_and_finish_handlers(qapp, tmp_path):
    nd = _donusturucu()

    nd._on_output()                                   # process None -> don
    nd._process = NS(
        readAllStandardOutput=lambda: NS(data=lambda: b"satir1\n\nsatir2\n"))
    yakalanan = []
    nd.output_line.emit = lambda m: yakalanan.append(m)
    nd._on_output()
    assert yakalanan == ["  satir1", "  satir2"]

    nd._cancelled = True
    nd._on_makepkg_finished(0, None)                  # 238-239
    assert nd.sonuc[-1][1] == "İptal edildi"

    nd._cancelled = False
    nd._on_makepkg_finished(2, None)                  # 242-243
    assert "makepkg başarısız" in nd.sonuc[-1][1]

    nd._find_output_package = lambda: None            # 251
    nd._on_makepkg_finished(0, None)
    assert "bulunamadı" in nd.sonuc[-1][1]

    nd._on_error("patlama")                           # 254
    assert "hatası" in nd.sonuc[-1][1]


def test_find_output_package_paths(qapp, tmp_path):
    nd = _donusturucu()
    nd._work_dir = tmp_path
    assert nd._find_output_package() is None          # hicbir dizin yok -> 266

    pkgout = tmp_path / "native_build" / "pkgout"
    pkgout.mkdir(parents=True)
    assert nd._find_output_package() is None          # bos -> devam

    paket = pkgout / "demo-1.0-1-x86_64.pkg.tar.zst"
    paket.write_bytes(b"P")
    bulundu = nd._find_output_package()
    assert bulundu == paket