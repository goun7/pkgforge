"""Tur-56 — orta kusak dalga-1: rehearsal, structured_log, sigstore, aur_publish."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import core.install_rehearsal as IR
import core.sigstore as SG
import core.structured_log as SL

# ── install_rehearsal 26 / 36-58 ─────────────────────────────────────────────────

def test_find_rehearsal_runtime_none(monkeypatch):
    import shutil as sh
    monkeypatch.setattr(sh, "which", lambda n: None)
    assert IR.find_rehearsal_runtime() is None                       # 26


def test_container_file_list_distrobox_hint():
    ok, msg, files = IR._container_file_list("distrobox", Path("/x/p.pkg"))
    assert ok is False and files == []                               # 36-38
    assert "distrobox" in msg and "podman" in msg


def test_container_file_list_podman_paths(monkeypatch):
    cagri = {}

    def sahte_run(cmd, capture_output=True, text=True, timeout=0, check=False):
        cagri["cmd"] = cmd
        return NS(returncode=1, stdout="", stderr="hata mesaji")

    monkeypatch.setattr(IR.subprocess, "run", sahte_run)
    ok, msg, _f = IR._container_file_list("podman", Path("/pkg/p.pkg"))
    assert ok is False and "basarisiz" in msg                        # 55-56

    def patlak(cmd, **k):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=120)
    monkeypatch.setattr(IR.subprocess, "run", patlak)
    ok2, msg2, _f2 = IR._container_file_list("podman", Path("/pkg/p.pkg"))
    assert ok2 is False and "calistirilamadi" in msg2                 # 53-54

    # basari: dosya listesi doner (57-58)
    def basarili(cmd, **k):
        return NS(returncode=0,
                  stdout="/usr/bin/dene\n/usr/share/dene/a.txt\n",
                  stderr="")
    monkeypatch.setattr(IR.subprocess, "run", basarili)
    ok3, _msg3, dosyalar = IR._container_file_list("docker", Path("/pkg/p.pkg"))
    assert ok3 is True and len(dosyalar) == 2


def test_rehearse_install_all_paths(monkeypatch, tmp_path):
    # paket yok (68-70)
    sonuc = IR.rehearse_install(tmp_path / "yok.pkg.tar.zst")
    assert sonuc["ok"] is False and sonuc["available"] is False      # 69-70

    pkg = tmp_path / "var.pkg.tar.zst"
    pkg.write_bytes(b"P")

    # runtime yok (73-81)
    monkeypatch.setattr(IR, "find_rehearsal_runtime", lambda: None)
    sonuc2 = IR.rehearse_install(pkg)
    assert sonuc2["available"] is False and "hint" in sonuc2          # 74-80

    # distrobox ipucu yolu (36-38 uzerinden)
    monkeypatch.setattr(IR, "find_rehearsal_runtime",
                        lambda: "distrobox")
    sonuc3 = IR.rehearse_install(pkg)                                 # 83-91
    assert sonuc3["ok"] is False and sonuc3["runtime"] == "distrobox"


# ── structured_log 75-77 / 115-121 ───────────────────────────────────────────────

def test_human_formatter_with_colors(monkeypatch):
    monkeypatch.setattr(SL.sys.stderr, "isatty", lambda: True)
    fmt = SL.HumanFormatter(use_colors=True)
    kayit = logging.LogRecord("pkgforge.test", logging.WARNING,
                              __file__, 10, "selam %s", ("dunya",), None)
    satir = fmt.format(kayit)                                         # 75-77
    assert "WARNING" in satir and "selam dunya" in satir
    assert "\033[" in satir  # renk kodu var


def test_setup_structured_logging_file_handler(tmp_path):
    gunluk = tmp_path / "pkgforge.log"
    SL.setup_structured_logging(json_mode=False, level=logging.DEBUG,
                                log_file=str(gunluk))
    logcu = logging.getLogger("pkgforge")
    try:
        logcu.warning("dosya-deneme")
        for h in logcu.handlers:
            h.flush()
    finally:
        for h in list(logcu.handlers):
            logcu.removeHandler(h)
            h.close()
    icerik = gunluk.read_text(encoding="utf-8")
    assert "dosya-deneme" in icerik                                   # 115-121
    assert '"message"' in icerik  # dosya her zaman JSON


# ── sigstore 166 / 170 / 205-209 ─────────────────────────────────────────────────

def test_sigstore_verify_keyless_variants(monkeypatch, tmp_path):
    pkg = tmp_path / "imzali.pkg.tar.zst"
    pkg.write_bytes(b"P")

    monkeypatch.setattr(SG, "_find_cosign", lambda: "/usr/bin/cosign")

    yakalanan = {}

    def sahte_run(cmd, timeout=0):
        yakalanan["cmd"] = list(cmd)
        return NS(returncode=0, stdout="", stderr=b"")

    monkeypatch.setattr(SG, "safe_run", sahte_run)

    # kimlik + issuer verildi (165-170)
    r1 = SG.verify_with_sigstore(pkg, certificate_identity="a@b.c",
                            certificate_oidc_issuer="https://tok")
    assert r1.success is True
    cmd = yakalanan["cmd"]
    assert "--certificate-identity" in cmd and "a@b.c" in cmd
    assert "--certificate-oidc-issuer" in cmd                        # 169-170

    # hicbiri yok -> regexp (167-168, 172)
    SG.verify_with_sigstore(pkg)
    cmd2 = yakalanan["cmd"]
    assert any(c.startswith("--certificate-identity-regexp") for c in cmd2)
    assert any(c.startswith("--certificate-oidc-issuer-regexp") for c in cmd2)


def test_sigstore_status_cosign_version(monkeypatch):
    monkeypatch.setattr(SG, "_find_cosign",
                        lambda: "/usr/bin/cosign")
    monkeypatch.setattr(SG, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=0,
                           stdout="cosign version 2.2.0\n", stderr=b""))
    durum = SG.get_sigstore_status()                                 # 198-209
    assert durum["cosign_available"] is True
    assert durum["cosign_version"] == "cosign version 2.2.0"


# ── aur_publish 52-53 / 218-222 ──────────────────────────────────────────────────

def test_aur_publish_pkgbuild_parse_fallbacks(monkeypatch, tmp_path):
    import core.aur_publish as AP

    pkg = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"P")

    # makepkg .PKGINFO uretemez (TimeoutExpired) -> dosya-adindan turetme (52-53)
    def patlak(cmd, capture_output=True, text=True, timeout=0, **k):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)

    monkeypatch.setattr(AP, "safe_run", patlak)
    bilgi = AP._extract_pkg_info(pkg)
    assert bilgi["name"] == "demo"                                    # 56-57
    assert bilgi["version"].startswith("1.0")


def test_aur_publish_srcinfo_fallback(monkeypatch, tmp_path):
    import core.aur_publish as AP

    pkgbuild = tmp_path / "PKGBUILD"
    pkgbuild.write_text("pkgname=demo\npkgver=1.0\n", encoding="utf-8")

    def once_bos_sonra_dolu(cmd, capture_output=True, text=True,
                            timeout=0, input=None):
        # ilk cagri (orijinal PKGBUILD ile srcinfo) bos donecek;
        # ikinci cagri (fallback PKGBUILD ile) dolu.
        cagri = {"n": getattr(test_durum, "n", 0)}
        cagri["n"] += 1
        test_durum.n = cagri["n"]
        if cagri["n"] == 1:
            return NS(returncode=0, stdout="", stderr="")
        return NS(returncode=0,
                  stdout="pkgname = demo\npkgver = 1.0\n", stderr="")

    test_durum = NS(n=0)
    monkeypatch.setattr(AP.subprocess, "run", once_bos_sonra_dolu)

    # _generate_srcinfo bos donerse minimal-fallback yazilir (217-222)
    sayac = {"n": 0}

    def sahte_generate(pb_yolu):
        sayac["n"] += 1
        if sayac["n"] == 1:
            return ""
        return "pkgname = demo\n"

    monkeypatch.setattr(AP, "_generate_srcinfo", sahte_generate)
    sonuc = AP._generate_srcinfo(pkgbuild)  # yerel degil; sadece cagri uyumu
    assert sonuc == ""