"""Tur-35 — compatibility_checker ortasi ve paylasilan-kutuphane blogu."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import core.compatibility_checker as CC
from core.compatibility_checker import CheckSeverity

ARACLAR = NS(bsdtar="bsdtar", file_cmd="file", readelf="readelf",
             objdump="objdump", ldd="ldd", pacman="pacman", namcap="namcap")


def _safe(cikti="", donus=0):
    return lambda cmd, timeout=0, **k: NS(returncode=donus,
                                          stdout=cikti, stderr="")


def test_run_namcap_branches(monkeypatch):
    monkeypatch.setattr(CC, "safe_run", _safe())
    sonuc = CC._run_namcap(Path("/x.pkg.tar.zst"),
                           NS(**{**vars(ARACLAR), "namcap": None}))
    assert sonuc.severity == CheckSeverity.WARNING               # 146-151

    monkeypatch.setattr(CC, "safe_run", _safe("", 0))
    assert CC._run_namcap(Path("/x"), ARACLAR).severity ==         CheckSeverity.PASS                                       # 157-162

    # hata + uyari karisimi
    monkeypatch.setattr(
        CC, "safe_run",
        _safe("paket.sh E: script bulundu\npaket.sh W: optbagimlik"))
    r = CC._run_namcap(Path("/x"), ARACLAR)                      # 171-184
    assert r.severity == CheckSeverity.ERROR and len(r.details) == 2

    # yalniz uyari; bilinmeyen satir da uyari sayilir
    monkeypatch.setattr(CC, "safe_run",
                        _safe("siradan satir\n(W) etiketli"))
    r = CC._run_namcap(Path("/x"), ARACLAR)                      # 173-191
    assert r.severity == CheckSeverity.WARNING and len(r.details) == 2


def test_check_dependencies_branches(monkeypatch):
    bos = CC._check_dependencies([], ARACLAR)
    assert bos[0].severity == CheckSeverity.PASS                 # 204-211

    cagrilar = []
    def sahte(cmd, timeout=0, **k):
        cagrilar.append(cmd)
        if "-Qi" in cmd:
            return NS(returncode=1, stdout="", stderr="")
        if "-Si" in cmd:
            return NS(returncode=0, stdout="", stderr="")        # 236-237
        return NS(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(CC, "safe_run", sahte)
    sonuclar = CC._check_dependencies(["gtk3>=3.24"], ARACLAR)
    assert any(r.severity == CheckSeverity.PASS for r in sonuclar)

    # gecersiz ad -> eksik olarak isaretlenir
    monkeypatch.setattr(CC, "safe_run",
                        lambda cmd, timeout=0, **k: NS(returncode=1,
                                                       stdout="", stderr=""))
    sonuclar = CC._check_dependencies(["kötü;rm -rf"], ARACLAR)   # 224-225
    assert any("geçersiz" in (r.message or "") or r.severity !=
               CheckSeverity.PASS for r in sonuclar)


def test_check_shared_libraries_full_flow(monkeypatch, tmp_path):
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")

    elf_icerik = b"ELF" + b"x" * 40
    def sahte_extract(cmd, timeout=0, **k):
        if "-xf" in cmd:
            hedef = Path(cmd[cmd.index("-C") + 1])
            (hedef / "usr" / "lib").mkdir(parents=True, exist_ok=True)
            (hedef / "usr" / "lib" / "demo.so").write_bytes(elf_icerik)
            (hedef / "lib.so.1").write_bytes(elf_icerik)   # paket icinde
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(CC, "safe_run", sahte_extract)

    # file mime -> x-sharedlib ; readelf DT_NEEDED -> libeksik.so.1
    def sahte_analiz(cmd, timeout=0, **k):
        if "--mime-type" in cmd:
            return NS(returncode=0,
                      stdout="application/x-sharedlib; charset=binary",
                      stderr="")
        if "-d" in cmd and "readelf" in cmd[0]:
            return NS(returncode=0,
                      stdout="(NEEDED) Shared library: [libeksik.so.1]\n"
                             "(NEEDED) Shared library: [libc.so.6]",
                      stderr="")
        if "--version-info" in cmd:
            return NS(returncode=0, stdout="GLIBC_2.34(GLIBC_2.4)", stderr="")
        return NS(returncode=0, stdout="", stderr="")
    def karma(cmd, timeout=0, **k):
        if cmd[:2] == [str(ARACLAR.bsdtar), "-xf"]:
            return sahte_extract(cmd, timeout=timeout, **k)
        if "-tf" in cmd:
            return NS(returncode=0,
                      stdout="usr/lib/demo.so\nlib.so.1\nusr/bin/arac",
                      stderr="")
        return sahte_analiz(cmd, timeout=timeout, **k)
    monkeypatch.setattr(CC, "safe_run", karma)

    monkeypatch.setattr(CC, "_system_lib_sonames", lambda: {"libc.so.6"})
    monkeypatch.setattr(CC, "_get_system_glibc", lambda t: "2.31")

    r = CC._check_shared_libraries(pkg, ARACLAR)                  # 368-461
    assert r.severity == CheckSeverity.ERROR
    assert "glibc" in r.message
    assert any("libeksik.so.1" in d for d in r.details)

    # yalniz eksik kutuphane (glibc sorunsuz)
    def temiz_versiyon(cmd, timeout=0, **k):
        if "--version-info" in cmd:
            return NS(returncode=0, stdout="GLIBC_2.17(x)", stderr="")
        return karma(cmd, timeout=timeout, **k)
    monkeypatch.setattr(CC, "safe_run", temiz_versiyon)
    r = CC._check_shared_libraries(pkg, ARACLAR)                  # 453-459
    assert r.severity == CheckSeverity.WARNING

    # her seyi taniyan sistem: PASS
    monkeypatch.setattr(CC, "_system_lib_sonames",
                        lambda: {"libc.so.6", "libeksik.so.1"})
    r = CC._check_shared_libraries(pkg, ARACLAR)                  # 460-464
    assert r.severity == CheckSeverity.PASS
    assert "1 ELF" in r.message or "analiz edildi" in r.message


def test_check_shared_libraries_edges(monkeypatch, tmp_path):
    # ELF yok -> erken donus (liste basarili ama bos)
    monkeypatch.setattr(CC, "safe_run",
                        lambda cmd, timeout=0, **k: NS(returncode=0,
                                                       stdout="", stderr=""))
    r = CC._check_shared_libraries(tmp_path / "bos.pkg.tar.zst", ARACLAR)
    assert r.severity == CheckSeverity.PASS                       # 360-365

    # supheli arsiv uyesi ve disari cikan yol atlanir
    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")
    def sahte(cmd, timeout=0, **k):
        if "-xf" in cmd:
            hedef = Path(cmd[cmd.index("-C") + 1])
            (hedef / "d").mkdir(parents=True, exist_ok=True)
            (hedef / "d" / "koto.so").write_bytes(b"ELFxxxx")
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(CC, "safe_run", sahte)
    monkeypatch.setattr(CC, "_system_lib_sonames", lambda: set())

    def liste(cmd, timeout=0, **k):
        if "-tf" in cmd:
            return NS(returncode=0,
                      stdout="../../etc/shadow\n/abs/x\nd/koto.so\n",
                      stderr="")
        return NS(returncode=1, stdout="", stderr="")

    def karma2(cmd, timeout=0, **k):
        if "-tf" in cmd:
            return liste(cmd, timeout=timeout, **k)
        return mime_exec(cmd, timeout=timeout, **k)
    monkeypatch.setattr(CC, "safe_run", karma2)

    def mime_exec(cmd, timeout=0, **k):
        if "--mime-type" in cmd:
            return NS(returncode=0, stdout="application/x-executable",
                      stderr="")                                   # 399
        if "-d" in cmd:
            raise RuntimeError("readelf patladi")                  # 421-423
        return NS(returncode=0, stdout="", stderr="")
    r = CC._check_shared_libraries(pkg, ARACLAR)                   # 386-392
    assert r.severity == CheckSeverity.PASS


def test_helper_functions(monkeypatch):
    # _system_lib_sonames: ldconfig yok
    import shutil as sh
    monkeypatch.setattr(sh, "which", lambda n: None)
    assert CC._system_lib_sonames() == set()                       # 474-476

    monkeypatch.setattr(sh, "which", lambda n: "/usr/bin/ldconfig")
    monkeypatch.setattr(CC, "safe_run",
                        lambda cmd, timeout=0, **k: (_ for _ in ()).throw(
                            RuntimeError("yok")))
    assert CC._system_lib_sonames() == set()                       # 479-481

    monkeypatch.setattr(CC, "safe_run", _safe(
        "      libc.so.6 => /usr/lib/libc.so.6\nbozuk-satir"))
    soname = CC._system_lib_sonames()                              # 484-489
    assert "libc.so.6" in soname

    # _elf_max_glibc: readelf yok / hata / boss
    assert CC._elf_max_glibc(Path("/x"),
                             NS(**{**vars(ARACLAR), "readelf": None})) == ""
    monkeypatch.setattr(CC, "safe_run",
                        lambda cmd, timeout=0, **k: (_ for _ in ()).throw(
                            RuntimeError("patladi")))
    assert CC._elf_max_glibc(Path("/x"), ARACLAR) == ""            # 502-504
    monkeypatch.setattr(CC, "safe_run", _safe("ilgincsiz"))
    assert CC._elf_max_glibc(Path("/x"), ARACLAR) == ""

    # _get_system_glibc: ldd yok / hata / bulunamadi
    assert CC._get_system_glibc(NS(**{**vars(ARACLAR), "ldd": None})) == ""
    monkeypatch.setattr(CC, "safe_run",
                        lambda cmd, timeout=0, **k: (_ for _ in ()).throw(
                            RuntimeError("yok")))
    assert CC._get_system_glibc(ARACLAR) == ""                     # 525-527
    monkeypatch.setattr(CC, "safe_run", _safe("versiyon yok"))
    assert CC._get_system_glibc(ARACLAR) == ""

    assert CC._version_gt("2.34", "2.31") is True                  # 530+
    assert CC._version_gt("2.3", "2.31") is False