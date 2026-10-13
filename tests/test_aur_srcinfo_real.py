"""AUR hazirlama/push sözleşmesi: .SRCINFO gercekten uretilmeli, yoksa erken durmali.

Neden var: _generate_pkgbuild makedepends'i hic bagimlilik yokken `makedepends=('')`
olarak yaziyordu. makepkg bunu "makedepends boş olamaz" ile reddediyor, dolayisiyla
`--printsrcinfo` HICBIR ZAMAN .SRCINFO üretmiyordu. Eski kodda .SRCINFO eksikligi
sessizce yutuluyordu: `prepare_aur_package` basarili donuyor, sonra `push_to_aur`
`git add PKGBUILD .SRCINFO` adiminda anlasilmaz bir hatayla kullanicida kaliyordu.
Bu dosya hem kok nedene hem de 'sessiz devam' davranisini kilitler.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

from core.aur_publish import (
    _MAKEDEPENDS,
    _generate_pkgbuild,
    _generate_srcinfo,
    prepare_aur_package,
    push_to_aur,
)

BUILD_SISTEMLERI = ("make", "cmake", "meson", "cargo", "python", "autotools", "unknown")


def _makedepends_satiri(pkgbuild: str) -> str:
    for satir in pkgbuild.splitlines():
        if satir.startswith("makedepends="):
            return satir
    raise AssertionError("makedepends satiri yok")


@pytest.mark.parametrize("sistem", BUILD_SISTEMLERI)
def test_makedepends_hic_bos_oge_icermez(sistem: str) -> None:
    satir = _makedepends_satiri(_generate_pkgbuild("demo", "1.0.0-2", "", sistem))
    assert "('')" not in satir.replace(" ", ""), satir
    assert satir.startswith("makedepends=(")


def test_python_makedepends_dort_ayri_oge() -> None:
    satir = _makedepends_satiri(_generate_pkgbuild("demo", "1.0", "", "python"))
    # tek bir "'python-build python-installer ...'" ogesi makepkg'te gecersizdir
    ogeler = satir[len("makedepends=("):-1].split("' '")
    assert len(_MAKEDEPENDS["python"]) == 4
    assert len(ogeler) == 4, ogeler
    assert "python-setuptools" in ogeler[0]


@pytest.mark.skipif(shutil.which("makepkg") is None, reason="makepkg yok")
@pytest.mark.parametrize("sistem", BUILD_SISTEMLERI)
def test_gercek_makepkg_srcinfo_uretiyor(sistem: str, tmp_path: pathlib.Path) -> None:
    yol = tmp_path / "PKGBUILD"
    yol.write_text(_generate_pkgbuild("demo", "1.0.0-2", "", sistem), encoding="utf-8")
    srcinfo = _generate_srcinfo(yol)
    assert srcinfo, f"{sistem}: .SRCINFO bos"
    assert "pkgbase = demo" in srcinfo


@pytest.mark.skipif(shutil.which("makepkg") is None, reason="makepkg yok")
def test_prepare_hiki_dosyayi_da_yazir(tmp_path: pathlib.Path) -> None:
    pkg = pathlib.Path(__file__).resolve().parent.parent / (
        "utest/lictest/lictest-1.0.0-1-any.pkg.tar.zst")
    if not pkg.is_file():
        pytest.skip("lictest fixture'i yok")
    ok, _mesaj, aur = prepare_aur_package(pkg, tmp_path)
    assert ok and aur is not None
    dizin = pathlib.Path(aur.pkgbuild).parent
    assert pathlib.Path(aur.pkgbuild).is_file()
    assert pathlib.Path(aur.srcinfo).is_file()
    assert "pkgbase = " in pathlib.Path(aur.srcinfo).read_text(encoding="utf-8")
    assert dizin == tmp_path / aur.name


def test_srcinfo_uretilemezse_hazirlama_basarisiz_donuyor(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # makepkg'un oldugu makinede de deterministik kirmizi yol: helper'i bos dondur.
    monkeypatch.setattr("core.aur_publish._generate_srcinfo", lambda _p: "")
    pkg = tmp_path / "deneme-1.0-1-any.pkg.tar.zst"
    pkg.write_bytes(b"\x00")
    ok, mesaj, aur = prepare_aur_package(pkg, tmp_path)
    assert ok is False and aur is None
    assert ".SRCINFO" in mesaj


def test_push_eksik_dosyalarla_erken_durur(tmp_path: pathlib.Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git yok")
    y = tmp_path / "only-pkgbuild"
    y.mkdir()
    (y / "PKGBUILD").write_text("pkgname=yok\n", encoding="utf-8")
    ok, mesaj = push_to_aur(y, "ssh://aur@example.invalid/x.git")[:2]
    assert ok is False and ".SRCINFO" in mesaj

    bos = tmp_path / "empty"
    bos.mkdir()
    ok2, mesaj2 = push_to_aur(bos, "ssh://aur@example.invalid/x.git")[:2]
    assert ok2 is False and "PKGBUILD" in mesaj2 and ".SRCINFO" in mesaj2


@pytest.mark.skipif(shutil.which("makepkg") is None, reason="makepkg yok")
def test_printsrcinfo_basarisizliginda_hata_mesaji_govdede_degil(
    tmp_path: pathlib.Path,
) -> None:
    # makepkg stderr'i Turkce yerellestirilebiliyor; kod yalnizca rc'ye bakar.
    yol = tmp_path / "PKGBUILD"
    yol.write_text('pkgname=demo\npkgver=1\npkgrel=1\narch=(x86_64)\n'
                   'makedepends=(")\n', encoding="utf-8")
    res = subprocess.run(["makepkg", "--printsrcinfo"], cwd=str(tmp_path),
                         capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert _generate_srcinfo(yol) == ""
