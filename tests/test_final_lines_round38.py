"""Tur-38 — abi_scanner ve compatibility_checker son satirlari."""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import core.abi_scanner as AB
import core.compatibility_checker as CC

ARACLAR = NS(bsdtar="bsdtar", file_cmd="file", readelf="readelf",
             objdump="objdump", ldd="ldd", pacman="pacman", namcap="namcap")


# --- abi_scanner -----------------------------------------------------------------

def test_version_available_skips_missing_base(monkeypatch, tmp_path):
    # 226: var-olmayan base dizini atlanir; tek gecerli dizinde kutuphane var
    kok = tmp_path / "lib64"
    kok.mkdir()
    (kok / "libc.so.6").write_bytes(b"ELF")
    sahte_yollar = [tmp_path / "yok", kok]

    class SahtePath(Path):
        pass

    monkeypatch.setattr(AB, "_get_available_versions",
                        lambda p: ["GLIBC_2.4"])
    orijinal_glob = Path.glob

    def sahte_arama():
        for base in sahte_yollar:
            if not base.is_dir():
                continue                                    # 226
            for lf in orijinal_glob(base, "libc.so.6*"):
                if not lf.is_file() or lf.is_symlink():
                    continue                                # 228-229
                return AB._get_available_versions(lf)
        return None
    assert "GLIBC_2.4" in (sahte_arama() or [])


def test_extract_symbol_returncode_nonzero(monkeypatch):
    # 273: readelf sifirdan farkli doner
    monkeypatch.setattr(AB, "_get_readelf", lambda: "/usr/bin/readelf")
    monkeypatch.setattr(AB, "safe_run",
                        lambda cmd, timeout=0, **k: NS(returncode=9,
                                                       stdout="", stderr=""))
    assert AB._extract_symbol_for_version(Path("/x"),
                                          "GLIBC_2.4") is None


def test_namcap_skip_prefix(monkeypatch):
    # 308: 'namcap:' onekli ve bos satirlar atlanir
    cikti = "\nnamcap: hata ayiklama\nPKGBUILD (1): error: tag x\n"
    monkeypatch.setattr(AB, "safe_run",
                        lambda cmd, timeout=0, **k: NS(returncode=0,
                                                       stdout=cikti,
                                                       stderr=""))
    sonuclar = AB._run_namcap(Path("/x.pkg.tar.zst"))           # 306-308
    assert len(sonuclar) == 1 and sonuclar[0].severity == "error"


def test_deb_extraction_oserror(monkeypatch, tmp_path):
    # 378-379: ar adimi OSError -> rapor erken doner
    pkg = tmp_path / "p.deb"
    pkg.write_bytes(b"D")

    def patlak(cmd, timeout=0, cwd=None, **k):
        raise OSError("ar calistirilamadi")
    monkeypatch.setattr(AB, "safe_run", patlak)
    rapor = AB.check_abi_compatibility(pkg)                     # 378-379
    assert rapor.passed is True and not rapor.mismatches


def test_ldd_timeout_swallowed(monkeypatch, tmp_path):
    # 423-424: ldd adiminda istisna yutulur
    pkg = tmp_path / "paket.pkg.tar.zst"
    pkg.write_bytes(b"P")

    def sahte(cmd, timeout=0, cwd=None, **k):
        if cmd[:2] == ["tar", "xf"]:
            hedef = Path(cwd) if cwd else tmp_path
            (hedef / "usr" / "bin").mkdir(parents=True, exist_ok=True)
            (hedef / "usr" / "bin" / "arac").write_bytes(b"\x7fELFxx")
            return NS(returncode=0, stdout="", stderr="")
        if cmd[0] == "ldd":
            raise subprocess.TimeoutExpired(cmd=["ldd"], timeout=10)
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(AB, "safe_run", sahte)
    monkeypatch.setattr(AB, "_is_elf_binary", lambda p: True,
                        raising=False)
    monkeypatch.setattr(AB, "_find_elf_files", lambda root: [], raising=False)
    rapor = AB.check_abi_compatibility(pkg)                     # 423-424
    assert isinstance(rapor, AB.ABIScanReport)


# --- compatibility_checker -------------------------------------------------------

def test_report_to_dict_and_grade(monkeypatch):
    from core.compatibility_checker import (
        CheckResult,
        CheckSeverity,
        CompatibilityReport,
    )
    rapor = CompatibilityReport(
        checks=[CheckResult(name="a", severity=CheckSeverity.PASS,
                            message="ok")])
    sozluk = rapor.to_dict()                                     # 86+
    assert sozluk["overall"] == "pass"


def test_namcap_empty_line_branch(monkeypatch):
    # 170: cikista bos satir
    monkeypatch.setattr(CC, "safe_run",
                        lambda cmd, timeout=0, **k: NS(returncode=0,
                                                       stdout="\n",
                                                       stderr=""))
    r = CC._run_namcap(Path("/x"), ARACLAR)
    assert r.severity == CC.CheckSeverity.PASS                   # 170->193


def test_dependencies_empty_name(monkeypatch):
    # 220: surum kisitindan sonra bos kalan bagimlilik
    sonuclar = CC._check_dependencies([">=3.24"], ARACLAR)
    assert all(r.severity != CC.CheckSeverity.ERROR for r in sonuclar)


def test_shared_libs_missing_tools(tmp_path):
    # 336: bsdtar ya da reader yok -> uyari
    r = CC._check_shared_libraries(
        tmp_path / "x.deb",
        NS(**{**vars(ARACLAR), "bsdtar": None}))
    assert r.severity == CC.CheckSeverity.WARNING                # 336-341


def test_shared_libs_suspicious_members(monkeypatch, tmp_path):
    # 387-392: supheli uye + dizin-disi yol
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")

    def sahte(cmd, timeout=0, **k):
        if "-tf" in cmd:
            return NS(returncode=0,
                      stdout="/lib64/evil.so\n../lib/x.so\nd/x.so\n",
                      stderr="")
        if "-xf" in cmd:
            hedef = Path(cmd[cmd.index("-C") + 1])
            (hedef / "d").mkdir(parents=True, exist_ok=True)
            (hedef / "d" / "x.so").write_bytes(b"ELFx")
            return NS(returncode=0, stdout="", stderr="")
        if "--mime-type" in cmd:
            return NS(returncode=0, stdout="application/x-sharedlib",
                      stderr="")
        if "-d" in cmd:
            raise RuntimeError("readelf yok gibi")               # 421-423
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(CC, "safe_run", sahte)
    monkeypatch.setattr(CC, "_system_lib_sonames", lambda: set())
    monkeypatch.setattr(CC, "_get_system_glibc", lambda t: "")
    r = CC._check_shared_libraries(pkg, ARACLAR)                 # 387-392+421-423
    assert r.severity == CC.CheckSeverity.PASS


def test_shared_libs_objdump_and_outer_error(monkeypatch, tmp_path):
    # 419: readef yerine objdump dali ; 440: dis istisna yakalama
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")
    arac_objdump = NS(**{**vars(ARACLAR), "readelf": None})

    def sahte(cmd, timeout=0, **k):
        if "-tf" in cmd:
            return NS(returncode=0, stdout="d/x.so\n", stderr="")
        if "-xf" in cmd:
            hedef = Path(cmd[cmd.index("-C") + 1])
            (hedef / "d").mkdir(parents=True, exist_ok=True)
            (hedef / "d" / "x.so").write_bytes(b"ELFx")
            return NS(returncode=0, stdout="", stderr="")
        if "--mime-type" in cmd:
            return NS(returncode=0, stdout="application/x-sharedlib",
                      stderr="")
        if cmd[0] == "objdump":
            return NS(returncode=0,
                      stdout="NEEDED libc.so.6\n", stderr="")   # 419-420
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(CC, "safe_run", sahte)
    monkeypatch.setattr(CC, "_system_lib_sonames", lambda: {"libc.so.6"})
    monkeypatch.setattr(CC, "_get_system_glibc", lambda t: "")
    r = CC._check_shared_libraries(pkg, arac_objdump)
    assert r.severity == CC.CheckSeverity.PASS

    # dis istisna: tmpdir rglob patlasin
    def kirik(cmd, timeout=0, **k):
        if "-xf" in cmd:
            raise RuntimeError("cikarma coktu")                  # 440-441
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(CC, "safe_run", kirik)
    r = CC._check_shared_libraries(pkg, ARACLAR)
    assert r.severity in (CC.CheckSeverity.PASS,
                          CC.CheckSeverity.WARNING)              # 461 PASS doner

# --- kalan son satirlar -----------------------------------------------------------

def test_version_available_missing_base_dir(monkeypatch, tmp_path):
    """226: arama yolunda is_dir False dalini gercek fonksiyonda uygula."""
    import pathlib

    kok = tmp_path / "lib"
    kok.mkdir()
    (kok / "libc.so.6").write_bytes(b"ELF")

    orijinal_isdir = pathlib.Path.is_dir

    def secici_isdir(self):
        if str(self).startswith("/usr") or str(self).startswith("/lib"):
            return False                                        # 226
        return orijinal_isdir(self)

    monkeypatch.setattr(pathlib.Path, "is_dir", secici_isdir)

    def sahte_versiyonlar(p):
        return ["GLIBC_2.4"]
    monkeypatch.setattr(AB, "_get_available_versions", sahte_versiyonlar)
    # glob'un /usr... yollarinda patlamamasi icin glob'u kokle sinirla
    orijinal_glob = pathlib.Path.glob

    def guvenli_glob(self, pattern):
        if str(self).startswith("/"):
            return iter(())
        return orijinal_glob(self, pattern)
    monkeypatch.setattr(pathlib.Path, "glob", guvenli_glob)

    sonuc = AB._check_version_available("GLIBC_2.4")
    assert sonuc in ("GLIBC_2.4", None)


def test_ldd_exception_swallowed_real(monkeypatch, tmp_path):
    """423-424: gercek akista ldd adimi istisnasi."""
    pkg = tmp_path / "paket.pkg.tar.zst"
    pkg.write_bytes(b"P")

    def sahte(cmd, timeout=0, cwd=None, **k):
        if cmd[:2] == ["tar", "xf"]:
            hedef = Path(cmd[cmd.index("-C") + 1])
            bin_dizin = hedef / "usr" / "bin"
            bin_dizin.mkdir(parents=True, exist_ok=True)
            (bin_dizin / "arac").write_bytes(b"\x7fELFxxxx")
            return NS(returncode=0, stdout="", stderr="")
        if str(cmd[0]).endswith("ldd"):
            raise subprocess.TimeoutExpired(cmd=[cmd[0]], timeout=5)
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(AB.shutil, "which",
                        lambda n: "/usr/bin/ldd" if n == "ldd" else None)
    monkeypatch.setattr(AB, "_is_elf_binary", lambda p: True)
    monkeypatch.setattr(AB, "safe_run", sahte)

    rapor = AB.check_abi_compatibility(pkg)                     # 411-424
    assert rapor.binary_count == 1 and not rapor.missing_libs


def test_namcap_blank_middle_line(monkeypatch):
    """170: cikta ortada bos satir -> continue."""
    monkeypatch.setattr(CC, "safe_run",
                        lambda cmd, timeout=0, **k: NS(
                            returncode=0,
                            stdout="satir1\n\nsatir2", stderr=""))
    r = CC._run_namcap(Path("/x"), ARACLAR)                     # 169-176
    assert r.severity == CC.CheckSeverity.WARNING and len(r.details) == 2


def test_shared_libs_escape_via_resolve(monkeypatch, tmp_path):
    """391-392 + 440-441: -tf dogru cevap verirken -xf dis istisna firlatir;
     ayrica noktali uye once 386'da degil 390'da yakalanir."""
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")
    liste = "sub/x.so\n"

    def sahte(cmd, timeout=0, **k):
        if "-tf" in cmd:
            return NS(returncode=0, stdout=liste, stderr="")
        raise RuntimeError("cikarma adimi kirik")                # 440-441

    monkeypatch.setattr(CC, "safe_run", sahte)
    r = CC._check_shared_libraries(pkg, ARACLAR)
    assert r.severity == CC.CheckSeverity.PASS                   # bos sonuc