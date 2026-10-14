"""Sinirli dosya gezintisi: kok dizinde takilmak/sayisiz girdi yok.

CI'da (ubuntu, Python 3.10) `core/sbom.py` -> `resolve_runtime_dependencies(Path("/"))`
zamana asimiyla kirdi; iz `is_elf_file` icindeki `open()` uzerindeydi. Sebep:
`Path.rglob("*")` butun dosya agacini (proc/sys/dev/run dahil) sinirsiz dolasuyor,
ozel girdilerin acilisi de bloklayabiliyordu. Artik gezinti bütçeli ve sanal
dizinler budaniyor.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import core.dep_resolver as DR
from config import ToolPaths


def _araclar(**kw: object) -> ToolPaths:
    taban = {k: "" for k in ToolPaths.__dataclass_fields__}
    taban.update(kw)
    return ToolPaths(**taban)  # type: ignore[arg-type]


def test_butceli_kadar_doner(tmp_path: Path) -> None:
    for i in range(30):
        (tmp_path / f"dosya{i}").write_bytes(b"\x00")
    hepsi = list(DR._dosya_gezintisi(tmp_path, 1000))
    assert len(hepsi) == 30
    butceli = list(DR._dosya_gezintisi(tmp_path, 10))
    assert len(butceli) < 10


def test_kok_dizinde_hizli_ve_sanal_dizin_yok() -> None:
    """Gercek '/' uzerinde: kisa surede doner, proc/sys/dev/run'a girmez."""
    bulunan = list(DR._dosya_gezintisi(Path("/"), 2000))
    assert bulunan, "kok dizinde hic dosya bulunamadi? test ortami beklenmedik"
    for yol in bulunan:
        metin = str(yol)
        assert not metin.startswith(("/proc/", "/sys/", "/dev/", "/run/")), metin


def test_sembole_baglar_izlenmez(tmp_path: Path) -> None:
    hedef = tmp_path / "gercek"
    hedef.mkdir()
    ic = hedef / "ic.bin"
    ic.write_bytes(b"\x7fELF")
    bag = tmp_path / "baglanti"
    try:
        bag.symlink_to(ic)
    except OSError:
        pytest.skip("sembolik bag olusturulamuyor")
    yollar = list(DR._dosya_gezintisi(tmp_path, 500))
    assert ic in yollar
    assert bag not in yollar


def test_okunamayan_dizin_yutuilur(tmp_path: Path) -> None:
    (tmp_path / "erisilemez").mkdir()
    (tmp_path / "gorunur.txt").write_bytes(b"x")
    os.chmod(tmp_path / "erisilemez", 0o000)
    try:
        yollar = list(DR._dosya_gezintisi(tmp_path, 500))
    finally:
        os.chmod(tmp_path / "erisilemez", 0o755)
    assert tmp_path / "gorunur.txt" in yollar


def test_collect_sonames_max_walk_parametresi_var(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"\x7fELF\x02\x01\x01")
    sonuc = DR.collect_sonames(tmp_path, _araclar(readelf="/usr/bin/readelf"),
                              max_walk=1)
    assert sonuc == set()


def test_collect_sonames_gercek_elf_oku(tmp_path: Path) -> None:
    readelf = "/usr/bin/readelf"
    if not Path(readelf).is_file():
        pytest.skip("readelf yok")
    # Sistemden kucuk bir ELF kopyala
    kaynak = Path("/bin/ls")
    if not kaynak.is_file():
        kaynak = Path("/usr/bin/ls")
    if not kaynak.is_file():
        pytest.skip("ornek ELF yok")
    kopya = tmp_path / "ls"
    kopya.write_bytes(kaynak.read_bytes())
    sonuc = DR.collect_sonames(tmp_path, _araclar(readelf=readelf))
    assert any(s.startswith("libc.so") for s in sonuc), sonuc
