"""Tur-37 — abi_scanner kalan dallar."""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import core.abi_scanner as AB


def _namcap(sev, tag="tag", msg="mesaj", dosya="PKGBUILD"):
    return NS(severity=sev, tag=tag, message=msg, file=dosya)


def test_summary_namcap_and_missing(monkeypatch):
    rapor = AB.ABIScanReport()
    rapor.binary_count = 3
    rapor.checked_symbols = 12
    rapor.namcap_available = True
    rapor.namcap_results = [_namcap("error"), _namcap("warning"),
                            _namcap("info"), NS(severity="diger",
                                                tag="t", message="m",
                                                file="")]
    ozet = rapor.summary()                                        # 83-87
    assert "Namcap:" in ozet and "1 hata" in ozet

    rapor.missing_libs = [("usr/bin/arac", "libyok.so.1")]         # 97-101
    rapor.namcap_results.append(_namcap("error", dosya=""))         # 102-108
    ozet = rapor.summary()
    assert "Eksik Kütüphaneler" in ozet
    assert "Namcap Bulguları" in ozet


def test_check_version_available_glibcxx(monkeypatch, tmp_path):
    # GLIBCXX dali (202-203): sahte kutuphane agaci
    kok = tmp_path / "usr" / "lib"
    kok.mkdir(parents=True)
    kutuphane = kok / "libstdc++.so.6"
    kutuphane.write_bytes(b"ELF")

    monkeypatch.setattr(AB, "_get_available_versions",
                        lambda p: ["GLIBCXX_3.4", "GLIBCXX_3.4.29"])
    sonuc = AB._check_version_available("GLIBCXX_3.4.29")
    assert sonuc == "GLIBCXX_3.4.29"                              # 200-203+

    # bilinmeyen on ek
    assert AB._check_version_available("CXXABI_1.3") is None      # 204-205


def test_extract_symbol_paths(monkeypatch):
    # readelf yok
    monkeypatch.setattr(AB, "_get_readelf", lambda: None)
    assert AB._extract_symbol_for_version(Path("/x"), "GLIBC_2.4") is None

    # readelf var ama cikis kodu bos
    monkeypatch.setattr(AB, "_get_readelf", lambda: "/usr/bin/readelf")
    monkeypatch.setattr(AB, "safe_run",
                        lambda cmd, timeout=0, **k: NS(returncode=0,
                                                       stdout="", stderr=""))
    assert AB._extract_symbol_for_version(Path("/x"),
                                          "GLIBC_2.4") is None    # 275-280

    # eslesen satir + sembol kolonu
    satir = "5: 0 0 FUNC G D GLIBC_2.4 printf"
    monkeypatch.setattr(AB, "safe_run",
                        lambda cmd, timeout=0, **k: NS(returncode=0,
                                                       stdout=satir,
                                                       stderr=""))
    sembol = AB._extract_symbol_for_version(Path("/x"), "GLIBC_2.4")
    assert sembol == "printf"                                      # 278-279


def test_run_namcap_exception_path(monkeypatch):
    def patlak(cmd, timeout=0, **k):
        raise subprocess.TimeoutExpired(cmd=["namcap"], timeout=10)
    monkeypatch.setattr(AB, "safe_run", patlak)
    sonuclar = AB._run_namcap(Path("/x.pkg.tar.zst"))              # 338-339
    assert sonuclar == []


def test_deb_extraction_branch(monkeypatch, tmp_path):
    pkg = tmp_path / "paket.deb"
    pkg.write_bytes(b"D")
    cagri = {"data_tar_cikti": False}

    def sahte(cmd, timeout=0, cwd=None, **k):
        if cmd[:1] == ["/bin/bash"]:
            hedef = Path(cwd) if cwd else tmp_path
            dt = hedef / "data.tar.zst"
            dt.write_text("")
            cagri["ar"] = True
            return NS(returncode=0, stdout="", stderr="")
        if cmd[0] == "tar":
            cagri["data_tar_cikti"] = True
            return NS(returncode=0, stdout="", stderr="")
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(AB, "safe_run", sahte)
    # ELF tarama adimlarini kisaltmak icin tarayiciyi bosaltilmis yap
    monkeypatch.setattr(AB, "_find_elf_files", lambda root: [],
                        raising=False)
    monkeypatch.setattr(AB, "ldd", None, raising=False)
    rapor = AB.check_abi_compatibility(pkg)                        # 362-379
    assert cagri.get("ar") is True
    assert cagri["data_tar_cikti"] is True
    assert rapor.passed is True