"""ELF analiz sadakati: readelf yerelleştirmesi, PIE ikilileri, yukleyici erisimi.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — readelf/objdump/ldd/f ILERİ GERİ CALISTIRILMAZ,
         safe_run ve yardimcilar monkeypatch; dosya yollari tmp_path.

Neden var (ikisi de GERCEK paketlerle yerelde olculen yanlis-pozitifler):
1. readelf ciktisi cagiranin locale'ine gore yerelleşir
   ("Shared library:" vs "Paylaşımlı kitaplık:"). Eski regex Ingilizce etiketi
   harfi harfine aradigi icin TR yerelinde parse sonames DONDURMUYORDU:
   bagimlilik cozumleme ve kutuphane kontrolu Turkce Arch kutucugunda sessizce
   hicbir sey yapmiyordu ("0 sonames -> 0 Arch packages", "tum kutuphaneler mevcut").
2. Modern toolchain ve TUM Arch paketleri PIE uretir ("application/x-pie-executable").
   Eski MIME filtresi yalnizca x-executable/x-sharedlib kabul ettigi icin her
   gercek ikili analizden SESSIZCE dusuyordu.
3. "Pakette var" != "yuklenebilir": Debian'in /usr/lib/x86_64-linux-gnu yolu
   Arch yukleyicisinin arama dizinlerinden biri degil; RPATH de karsilamıyorsa
   ikili acilista "libX.so => not found" verir.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import core.compatibility_checker as CC
from config import ToolPaths
from core.compatibility_checker import (
    _ELF_ANALYSABLE_MIMES,
    _lib_reachable,
    _loader_search_dirs,
    _read_ld_conf_paths_from_glob,
    _shared_lib_result,
    _shipped_lib_dirs,
)
from core.dep_resolver import (
    parse_needed_sonames,
    parse_objdump_rpath_dirs,
    parse_objdump_sonames,
    parse_rpath_dirs,
)

# Gercek `readelf -d` ciktilari (ayni ikilinin TR ve EN kosulari).
NEEDED_TR = (
    " 0x0000000000000001 (NEEDED)             "
    "Paylaşımlı kitaplık: [libdemo2.so]\n"
    " 0x0000000000000001 (NEEDED)             "
    "Paylaşımlı kitaplık: [libc.so.6]\n"
)
NEEDED_EN = (
    " 0x0000000000000001 (NEEDED)             "
    "Shared library: [libdemo2.so]\n"
    " 0x0000000000000001 (NEEDED)             "
    "Shared library: [libc.so.6]\n"
)
RUNPATH_TR = NEEDED_TR + (
    " 0x000000000000001d (RUNPATH)            "
    "Kitaplık çalışım yolu: [/usr/lib/x86_64-linux-gnu]\n"
)
RUNPATH_EN = NEEDED_EN + (
    " 0x000000000000001d (RUNPATH)            "
    "Library runpath: [/usr/lib/x86_64-linux-gnu]\n"
)
OBJDUMP = (
    "  NEEDED               libdemo.so\n"
    "  NEEDED               libc.so.6\n"
    "  RUNPATH              /usr/lib/x86_64-linux-gnu\n"
)


# == 1) yerellestirmeden bagimsiz DT_NEEDED / RPATH parsei ======================================

def test_needed_tr_locale_parse_edilir():
    """REGRESYON KILIDI: TR 'Paylaşımlı kitaplık' satiri artik ayrismali."""
    assert parse_needed_sonames(NEEDED_TR) == ["libdemo2.so", "libc.so.6"]


def test_needed_en_geriye_udumlu():
    assert parse_needed_sonames(NEEDED_EN) == ["libdemo2.so", "libc.so.6"]


def test_needed_bos_cikti():
    assert parse_needed_sonames("") == []
    assert parse_needed_sonames("There is no dynamic section in this file.") == []


def test_rpath_tr_ve_en_ayni_verir():
    assert parse_rpath_dirs(RUNPATH_TR) == ["/usr/lib/x86_64-linux-gnu"]
    assert parse_rpath_dirs(RUNPATH_EN) == ["/usr/lib/x86_64-linux-gnu"]


def test_rpath_yoksa_bos_liste():
    assert parse_rpath_dirs(NEEDED_TR) == []


def test_rpath_cok_dizinli_virgul_ayraci():
    """RUNPATH iki yolu ':' ile tasir -> ikisi de cikarilmali."""
    out = "(RUNPATH)            Library runpath: [/a/lib:/b/lib]\n"
    assert parse_rpath_dirs(out) == ["/a/lib", "/b/lib"]


def test_rpath_rpath_etiketi_de_karilanir():
    """Eski DT_RPATH (RUNPATH'den once) de taninmali."""
    out = "(RPATH)              Library rpath: [/opt/legacy/lib]\n"
    assert parse_rpath_dirs(out) == ["/opt/legacy/lib"]


def test_objdump_needed_ve_rpath():
    assert parse_objdump_sonames(OBJDUMP) == ["libdemo.so", "libc.so.6"]
    assert parse_objdump_rpath_dirs(OBJDUMP) == ["/usr/lib/x86_64-linux-gnu"]


def test_objdump_rpath_yok():
    assert parse_objdump_rpath_dirs(NEEDED_EN) == []


# == 2) PIE ikilileri analize girmeli ===========================================================

def test_pie_mime_kumesinde():
    assert "application/x-pie-executable" in _ELF_ANALYSABLE_MIMES


def _karma_sahte(runler: list[str]):
    """_check_shared_libraries'in gomulu akisini safe_run ile taklit eder."""

    def sahte(cmd, *a, **k):
        runler.append(" ".join(str(c) for c in cmd))
        ns = subprocess.CompletedProcess(args=list(map(str, cmd)), returncode=0,
                                         stdout="", stderr="")
        joined = " ".join(str(c) for c in cmd)
        if "-xf" in joined:
            hedef = Path(cmd[cmd.index("-C") + 1])
            (hedef / "usr" / "bin").mkdir(parents=True, exist_ok=True)
            (hedef / "usr" / "bin" / "arac").write_bytes(b"x")
        elif "-tf" in joined:
            ns.stdout = "usr/bin/arac\n"
        elif "--mime-type" in joined:
            ns.stdout = "application/x-pie-executable\n"
        elif "readelf" in joined and "-d" in joined:
            ns.stdout = NEEDED_TR.replace("libdemo2.so", "libyok.so.1")
        return ns

    return sahte


def test_pie_ikilisi_gercekten_analiz_edilir(monkeypatch, tmp_path):
    """REGRESYON KILIDI: PIE ikilisi filtrede dusurse checked_count 0 olurdu."""
    pkg = tmp_path / "p-1-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"P")
    araclar = ToolPaths(bsdtar="bsdtar", file_cmd="file", readelf="readelf",
                        ldd="ldd")
    cagrilar: list[str] = []
    monkeypatch.setattr(CC, "safe_run", _karma_sahte(cagrilar))
    monkeypatch.setattr(CC, "_system_lib_sonames", lambda: {"libc.so.6"})
    monkeypatch.setattr(CC, "_get_system_glibc", lambda t: "")
    monkeypatch.setattr(CC, "_loader_search_dirs", lambda: {"/usr/lib"})

    r = CC._check_shared_libraries(pkg, araclar)
    assert r.severity is CC.CheckSeverity.WARNING
    assert any("libyok.so.1" in d for d in r.details)


# == 3) yukleyici erisilebilirlik mantigi =======================================================

def _tmp(root: Path) -> Path:
    d = root / "extract"
    (d / "usr" / "lib" / "x86_64-linux-gnu").mkdir(parents=True)
    (d / "usr" / "bin").mkdir(parents=True)
    lib = d / "usr" / "lib" / "x86_64-linux-gnu" / "libdemo.so"
    lib.write_bytes(b"L")
    (d / "usr" / "bin" / "arac").write_bytes(b"B")
    return d


def test_dizin_arama_yolundaysa_erisilebilir(tmp_path):
    d = _tmp(tmp_path)
    lib = d / "usr" / "lib" / "x86_64-linux-gnu" / "libdemo.so"
    assert _lib_reachable(lib, d / "usr" / "bin" / "arac", d,
                          ["/usr/lib/x86_64-linux-gnu"], {"/usr/lib"}) is True


def test_arama_yolu_disinda_ve_rpathsiz_erisilemez(tmp_path):
    d = _tmp(tmp_path)
    lib = d / "usr" / "lib" / "x86_64-linux-gnu" / "libdemo.so"
    assert _lib_reachable(lib, d / "usr" / "bin" / "arac", d, [],
                          {"/usr/lib"}) is False


def test_kurulum_dizini_arama_yolu_ise_erisilebilir(tmp_path):
    d = _tmp(tmp_path)
    lib = d / "usr" / "lib" / "x86_64-linux-gnu" / "libdemo.so"
    assert _lib_reachable(lib, d / "usr" / "bin" / "arac", d, [],
                          {"/usr/lib", "/usr/lib/x86_64-linux-gnu"}) is True


def test_origin_rpath_kardes_dizini_karsilar(tmp_path):
    d = _tmp(tmp_path)
    sib = d / "usr" / "bin" / "libkardes.so"
    sib.write_bytes(b"S")
    assert _lib_reachable(sib, d / "usr" / "bin" / "arac", d,
                          ["$ORIGIN"], {"/usr/lib"}) is True


def test_origin_rpath_uymuyorsa_erisilemez(tmp_path):
    d = _tmp(tmp_path)
    lib = d / "usr" / "lib" / "x86_64-linux-gnu" / "libdemo.so"
    assert _lib_reachable(lib, d / "usr" / "bin" / "arac", d,
                          ["$ORIGIN"], {"/usr/lib"}) is False


# == _shipped_lib_dirs / _loader_search_dirs ==================================================

def test_shipped_lib_dirs_ad_ve_yolu_tasir(tmp_path):
    d = _tmp(tmp_path)
    m = _shipped_lib_dirs(d)
    assert set(m) == {"libdemo.so"}
    assert str(m["libdemo.so"][0].relative_to(d)) == \
        "usr/lib/x86_64-linux-gnu/libdemo.so"


def test_shipped_lib_dirs_versionli_son_ek(tmp_path):
    d = tmp_path / "e"
    (d / "usr" / "lib").mkdir(parents=True)
    (d / "usr" / "lib" / "libfoo.so.1").write_bytes(b"L")
    assert "libfoo.so.1" in _shipped_lib_dirs(d)


def test_loader_dirs_varsayilanlari_icerir():
    s = _loader_search_dirs()
    assert {"/usr/lib", "/lib"} <= s


def test_loader_dirs_okunamazsa_varsayilanlarla_donuer(monkeypatch):
    """ORTAM: /etc/ld.so.conf yoksa/okunamazsa crash YOK, intihaller doner."""
    def patla(*a, **k):
        raise OSError("izin yok")
    monkeypatch.setattr(Path, "read_text", patla)
    assert _loader_search_dirs() == {"/usr/lib", "/lib"}


def test_loader_dirs_duz_satirlari_toplar(monkeypatch):
    metin = "# yorum\n/opt/extra/lib\n\ninclude /tmp/yok/*.conf\n"
    monkeypatch.setattr(Path, "read_text", lambda self, **k: metin)
    s = _loader_search_dirs()
    assert "/opt/extra/lib" in s


def test_ld_conf_glob_expand(tmp_path):
    conf = tmp_path / "x.conf"
    conf.write_text("# yorum\n/opt/one/lib\n", encoding="utf-8")
    got = _read_ld_conf_paths_from_glob(str(tmp_path / "*.conf"))
    assert "/opt/one/lib" in got


def test_ld_conf_glob_bos_ve_yok_dizin():
    assert _read_ld_conf_paths_from_glob("/nonexistent/dir/*.conf") == set()


def test_ld_conf_glob_okunamayan_dosyayi_atlar(tmp_path, monkeypatch):
    """ORTAM: glob eslesse de dosya okunamiyasa crash YOK, sessiz atlanir."""
    (tmp_path / "a.conf").write_text("/ok/lib\n", encoding="utf-8")
    (tmp_path / "b.conf").write_text("/atlanır/lib\n", encoding="utf-8")

    gercek = Path.read_text

    def patla(self, *a, **k):
        if self.name == "b.conf":
            raise OSError("izin yok")
        return gercek(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", patla)
    got = _read_ld_conf_paths_from_glob(str(tmp_path / "*.conf"))
    assert got == {"/ok/lib"}


# == _shared_lib_result erisilemez dali ======================================================

def test_result_erisilemez_warning():
    r = _shared_lib_result([], [], 2, ["libdemo.so (arac)"])
    assert r.severity is CC.CheckSeverity.WARNING
    assert any("libdemo.so" in d for d in r.details)


def test_result_hem_eksik_hem_erisilemez():
    r = _shared_lib_result(["liba.so"], [], 3, ["libb.so (arac)"])
    assert r.severity is CC.CheckSeverity.WARNING
    assert any("liba.so" in d for d in r.details)
    assert any("libb.so" in d for d in r.details)


def test_result_glibc_oncelik_korur():
    """glibc sorunu varsa erisilemez detaylari mesajda ikinci planda kalir."""
    r = _shared_lib_result(["liba.so"], ["arac: GLIBC_2.99 gerekli"], 1, ["libb.so (x)"])
    assert r.severity is CC.CheckSeverity.ERROR


def test_result_varsayilan_none_erisilemez_listesi():
    assert _shared_lib_result([], [], 1).severity is CC.CheckSeverity.PASS


# == _analyze_elf_dependencies erisilemez akışı ==============================================

def test_analyze_erisilemez_libi_ayri_kutuya_koyar(monkeypatch, tmp_path):
    d = _tmp(tmp_path)
    lib = d / "usr" / "lib" / "x86_64-linux-gnu" / "libdemo.so"
    arac = d / "usr" / "bin" / "arac"

    def sahte(cmd, *a, **k):
        return subprocess.CompletedProcess(args=list(map(str, cmd)), returncode=0,
                                           stdout=NEEDED_TR.replace("libdemo2.so",
                                                                    "libdemo.so"),
                                           stderr="")

    monkeypatch.setattr(CC, "safe_run", sahte)
    monkeypatch.setattr(CC, "_system_lib_sonames", lambda: {"libc.so.6"})
    monkeypatch.setattr(CC, "_loader_search_dirs", lambda: {"/usr/lib"})
    monkeypatch.setattr(CC, "_get_system_glibc", lambda t: "")

    missing, glibc, count, unreach = CC._analyze_elf_dependencies([arac, lib], d,
                                                                 ToolPaths(readelf="readelf"))
    assert count == 2
    assert glibc == []
    assert missing == []          # kutuphane PAKETTE — 'eksik' degil
    assert any("libdemo.so" in u for u in unreach)   # ama YUKLENEBILIR degil


def test_analyze_rpathli_vaka_temiz(monkeypatch, tmp_path):
    """RPATH karsilıyorsa erisilemez listesi BOS kalmali (yanlis alarm yok)."""
    d = _tmp(tmp_path)
    arac = d / "usr" / "bin" / "arac"

    def sahte(cmd, *a, **k):
        return subprocess.CompletedProcess(args=list(map(str, cmd)), returncode=0,
                                           stdout=RUNPATH_TR.replace("libdemo2.so",
                                                                     "libdemo.so"),
                                           stderr="")

    monkeypatch.setattr(CC, "safe_run", sahte)
    monkeypatch.setattr(CC, "_system_lib_sonames", lambda: {"libc.so.6"})
    monkeypatch.setattr(CC, "_loader_search_dirs", lambda: {"/usr/lib"})
    monkeypatch.setattr(CC, "_get_system_glibc", lambda t: "")

    missing, _glibc, count, unreach = CC._analyze_elf_dependencies(
        [arac], d, ToolPaths(readelf="readelf"))
    assert missing == [] and unreach == [] and count == 1


def test_analyze_readelf_yoksa_objdump_yedegi(monkeypatch, tmp_path):
    d = _tmp(tmp_path)
    arac = d / "usr" / "bin" / "arac"

    def sahte(cmd, *a, **k):
        out = OBJDUMP.replace("libdemo.so", "libyok.so.1")
        return subprocess.CompletedProcess(args=list(map(str, cmd)), returncode=0,
                                           stdout=out, stderr="")

    monkeypatch.setattr(CC, "safe_run", sahte)
    monkeypatch.setattr(CC, "_system_lib_sonames", lambda: set())
    monkeypatch.setattr(CC, "_get_system_glibc", lambda t: "")

    missing, _glibc, _count, _unreach = CC._analyze_elf_dependencies(
        [arac], d, ToolPaths(objdump="objdump"))   # readelf YOK
    assert "libyok.so.1" in missing
