"""Debian -> Arch .INSTALL cevirmeni (opt-in --translate-scripts) testleri.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — ar/bsdtar GERCEK calistirilmaz, safe_run monkeypatch;
         yazma islemleri tmp_path.

Neden var: donusum Debian bakim betiklerini (postinst/postrm) sessizce dusuruyordu.
Simdi kullanaci isterse bunlari Arch'un .INSTALL kancasina cevirip pakete gomuyor;
varsayilan KAPALI, cunku ucuncu taraf kodunu kurulumda root calistirmak acik
onay istemelidir. Bu dosya ayni zamanda gercekten cikarilmis bir hatayi kilitler:
control.tar uyeleri arsip KOKUNDE durur ("./postinst"); "DEBIAN/postinst" aramak
hicbir sey bulamaz ve celiski sessiz kalirdi.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, ClassVar

import pytest

from core.subprocess_converters import NativeDebConverterSubprocess as N


class Araclar:
    ar: ClassVar[str] = "/usr/bin/ar"
    bsdtar: ClassVar[str] = "/usr/bin/bsdtar"


def _cp(out: Any = "", rc: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["x"], returncode=rc, stdout=out,
                                       stderr="")


def _converter(monkeypatch, responses) -> N:
    def sahte(cmd, *a, **k):
        return responses(cmd, *a, **k)
    monkeypatch.setattr("core.subprocess_converters.safe_run", sahte)
    return N(Araclar(), translate_scripts=True)


class Meta:
    name: ClassVar[str] = "pi-tool-pkg"
    version: ClassVar[str] = "1.0"
    arch_mapped: ClassVar[str] = "any"
    maintainer_scripts: ClassVar[list[str]] = ["postinst", "postrm"]


# == uzanti uyeleri: control.tar KOKTEN okunmali ==============================================

def test_kokteki_uyeler_cikarilir(monkeypatch, tmp_path):
    """REGRESYON KILIDI: './postinst' denenir; 'DEBIAN/postinst' ARANMAZ."""
    denenen: list[str] = []

    def responses(cmd, *a, **k):
        joined = " ".join(cmd)
        if " ar t " in joined or cmd[1:2] == ["t"]:
            return _cp("debian-binary\ncontrol.tar.xz\ndata.tar.xz\n")
        if cmd[1:2] == ["p"]:
            return _cp(out=b"CONTROLBLOB")
        # bsdtar -xf - --to-stdout <member>
        member = cmd[-1]
        denenen.append(member)
        if member == "./postinst":
            return _cp("#!/bin/sh\necho merhaba\n")
        return _cp(rc=1)

    c = _converter(monkeypatch, responses)
    got = c._extract_control_scripts(tmp_path / "x.deb", ["postinst", "postrm"])
    assert "postinst" in got and "merhaba" in got["postinst"]
    assert "postrm" not in got
    assert "./postinst" in denenen
    assert not any("DEBIAN/" in m for m in denenen), \
        f"control.tar kokte; DEBIAN/ oni aramak bos sonuc verir: {denenen}"


def test_on_eksik_varyant_da_denendigi(monkeypatch, tmp_path):
    """Bazi paketler './' onsuz yaziyor -> iki aday da denenmeli."""
    def responses(cmd, *a, **k):
        if cmd[1:2] == ["t"]:
            return _cp("control.tar.gz\n")
        if cmd[1:2] == ["p"]:
            return _cp(out=b"B")
        if cmd[-1] == "postrm":
            return _cp("rm -f /tmp/x\n")
        return _cp(rc=1)

    c = _converter(monkeypatch, responses)
    got = c._extract_control_scripts(Path("x.deb"), ["postinst", "postrm"])
    assert got == {"postrm": "rm -f /tmp/x\n"}


def test_ar_t_basarisizsa_bos_doner(monkeypatch):
    def responses(cmd, *a, **k):
        return _cp(rc=1)
    c = _converter(monkeypatch, responses)
    assert c._extract_control_scripts(Path("x.deb"), ["postinst"]) == {}


def test_control_tar_yoksa_bos(monkeypatch):
    def responses(cmd, *a, **k):
        if cmd[1:2] == ["t"]:
            return _cp("debian-binary\ndata.tar.xz\n")
        return _cp(rc=1)
    c = _converter(monkeypatch, responses)
    assert c._extract_control_scripts(Path("x.deb"), ["postinst"]) == {}


def test_ar_p_basarisizsa_bos(monkeypatch):
    def responses(cmd, *a, **k):
        if cmd[1:2] == ["t"]:
            return _cp("control.tar.xz\n")
        if cmd[1:2] == ["p"]:
            return _cp(rc=1)
        return _cp(rc=1)
    c = _converter(monkeypatch, responses)
    assert c._extract_control_scripts(Path("x.deb"), ["postinst"]) == {}


def test_bsdtar_yoksa_tar_yedegi_kullanimi(monkeypatch):
    """bsdtar bos ise 'tar -xf' dali denenir (arac yoklugu sessiz basari degil)."""
    gorulen: list[list[str]] = []

    def responses(cmd, *a, **k):
        gorulen.append(cmd)
        if cmd[1:2] == ["t"]:
            return _cp("control.tar.xz\n")
        if cmd[1:2] == ["p"]:
            return _cp(out=b"B")
        return _cp("./postinst icerigi\n")

    monkeypatch.setattr("core.subprocess_converters.safe_run", responses)
    c = N(type("T", (), {"ar": "/usr/bin/ar", "bsdtar": ""})(),
          translate_scripts=True)
    got = c._extract_control_scripts(Path("x.deb"), ["postinst"])
    assert got and "icerigi" in got["postinst"]
    assert any(cmd[0] == "tar" for cmd in gorulen)


# == _pkgname_for =================================================================================

@pytest.mark.parametrize("ad,beklenen", [
    ("Foo-Bar", "foo-bar"),
    ("a_b", "a_b"),
    ("Türk-çe", "t-rk--e"),  # u-ve-c harfleri ayri ayri "-" olur, birlestirme YOK          # gecersiz karakter -> '-'
    ("  spaced  ", "spaced"),
    ("@weird+pkg.name", "@weird+pkg.name"),
    ("---", "unknown-deb"),
    ("", "unknown-deb"),
])
def test_pkgname_for(ad, beklenen):
    c = N.__new__(N)
    assert c._pkgname_for(type("M", (), {"name": ad})()) == beklenen


def test_pkgname_for_generate_pkgbuild_ile_ayni():
    """install= dosya adi PKGBUILD'deki pkgname ile ayni turetilmek ZORUNDA."""
    c = N.__new__(N)
    meta = type("M", (), {"name": "Some Pkg", "version": "1.0",
                          "arch_mapped": "any", "depends": [],
                          "description": "", "url": "", "maintainer": ""})()
    assert c._pkgname_for(meta) == "some-pkg"


# == _write_translated_install ====================================================================

def _kurulum_dosyasi(monkeypatch, tmp_path, scripts=None, metinler=None):
    if metinler is None:   # 'or' kullanilamaz: bos dict varsayilanla ezilir
        metinler = {"postinst": "#!/bin/sh\necho merhaba\n",
                    "postrm": "#!/bin/sh\nrm -f /tmp/x\n"}

    def responses(cmd, *a, **k):
        if cmd[1:2] == ["t"]:
            return _cp("control.tar.xz\n")
        if cmd[1:2] == ["p"]:
            return _cp(out=b"B")
        m = cmd[-1].lstrip("./")
        return _cp(metinler.get(m, "")) if m in metinler else _cp(rc=1)

    c = _converter(monkeypatch, responses)
    src = tmp_path / "src"
    src.mkdir()
    (tmp_path / "build").mkdir(exist_ok=True)   # _do_convert bunu gercekte olusturur
    meta = type("M", (), {"name": "demo-pkg", "version": "1.0",
                          "maintainer_scripts": scripts
                          if scripts is not None else ["postinst", "postrm"]})()
    line = c._write_translated_install(tmp_path / "d.deb", src, tmp_path / "build",
                                       meta)
    return c, line, src


def test_install_satiri_dosya_adini_icerir(monkeypatch, tmp_path):
    _c, line, _src = _kurulum_dosyasi(monkeypatch, tmp_path)
    assert line == "\ninstall='demo-pkg.install'\n"


def test_install_dosyasi_build_dizinine_yazilir(monkeypatch, tmp_path):
    _c, _line, _src = _kurulum_dosyasi(monkeypatch, tmp_path)
    f = tmp_path / "build" / "demo-pkg.install"
    assert f.is_file()
    text = f.read_text(encoding="utf-8")
    assert "post_install()" in text and "post_remove()" in text
    assert "post_upgrade() { post_install; }" in text
    assert "/usr/share/pkgforge-maintainer/postinst configure" in text
    assert "/usr/share/pkgforge-maintainer/postrm remove" in text


def test_betik_kopyalari_src_dizinine_yazilir_ve_calistirilabilir(monkeypatch, tmp_path):
    _c, _line, src = _kurulum_dosyasi(monkeypatch, tmp_path)
    for name, content in (("postinst", "merhaba"), ("postrm", "rm -f")):
        p = src / "usr/share/pkgforge-maintainer" / name
        assert p.is_file()
        assert content in p.read_text(encoding="utf-8")
        assert p.stat().st_mode & 0o111, "paketlenen betik calistirilabilir olmali"


def test_bos_liste_satir_donmez(monkeypatch, tmp_path):
    """Cagri noktasindaki koruma: meta.maintainer_scripts bos ise _do_convert
    bu metodu HIC cagirmaz; metot da cikarilacak betik bulamazsa "" donerir ki
    PKGBUILD'e bos install= satiri girmesin.
    """
    _c, line, _src = _kurulum_dosyasi(monkeypatch, tmp_path, scripts=[],
                                     metinler={})
    assert line == ""
    assert not (tmp_path / "build" / "demo-pkg.install").exists()


def test_cikarma_bossa_satir_donmez(monkeypatch, tmp_path):
    """ORTAM: control.tar okunamazsa sessiz 'drop' — install= satiri YOK."""
    def responses(cmd, *a, **k):
        return _cp(rc=1)
    c = _converter(monkeypatch, responses)
    src = tmp_path / "src"; src.mkdir()
    meta = type("M", (), {"name": "demo", "version": "1",
                          "maintainer_scripts": ["postinst"]})()
    assert c._write_translated_install(Path("d.deb"), src,
                                       tmp_path / "b", meta) == ""


def test_pre_post_prerm_dordusu_cevrilir(monkeypatch, tmp_path):
    _c, _line, _src = _kurulum_dosyasi(
        monkeypatch, tmp_path,
        scripts=["preinst", "postinst", "prerm", "postrm"],
        metinler={k: "#!/bin/sh\n" for k in
                  ("preinst", "postinst", "prerm", "postrm")},
    )
    text = (tmp_path / "build" / "demo-pkg.install").read_text(encoding="utf-8")
    for hook in ("pre_install", "post_install", "pre_remove", "post_remove"):
        assert f"{hook}()" in text


def test_sira_belirli_ve_tekrarlanabilir(monkeypatch, tmp_path):
    """Ayni girdi -> bayt bayt ayni dosya (map ordered tuple; frozenset tuzağı)."""
    _c, _l, _s = _kurulum_dosyasi(monkeypatch, tmp_path)
    ilk = (tmp_path / "build" / "demo-pkg.install").read_text(encoding="utf-8")

    ikinci_kok = tmp_path / "ikinci"
    ikinci_kok.mkdir()
    _c2, _l2, _s2 = _kurulum_dosyasi(monkeypatch, ikinci_kok)
    ikinci = (ikinci_kok / "build" / "demo-pkg.install").read_text(encoding="utf-8")

    assert ilk == ikinci
    assert ilk.index("post_install()") < ilk.index("post_remove()")


def test_kismi_betikte_upgrade_yalnizca_postinst_varsa(monkeypatch, tmp_path):
    _c, _l, _s = _kurulum_dosyasi(monkeypatch, tmp_path, scripts=["postinst"],
                                 metinler={"postinst": "#!/bin/sh\n"})
    text = (tmp_path / "build" / "demo-pkg.install").read_text(encoding="utf-8")
    assert "post_upgrade() { post_install; }" in text
    assert "post_remove()" not in text


def test_postinst_yoksa_upgrade_kanci_uretilmez(monkeypatch, tmp_path):
    _c, _l, _s = _kurulum_dosyasi(monkeypatch, tmp_path, scripts=["postrm"],
                                 metinler={"postrm": "#!/bin/sh\n"})
    text = (tmp_path / "build" / "demo-pkg.install").read_text(encoding="utf-8")
    assert "post_upgrade" not in text


# == varsayilan kapali ==========================================================================

def test_bayrak_varsayilan_kapali():
    """Ortak karar: root'ta ucuncu taraf kodu yalnizca acik onayla calisir."""
    c = N(Araclar())
    assert c._translate_scripts is False
