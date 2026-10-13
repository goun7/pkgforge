"""C-locale ayristirma, completion surumu ve girdi dogrulama regresyonlari.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: pacman/ar/bsdtar gercekten calistirilmaz (safe_run monkeypatch); tek
         subprocess testi `main.py --help` (yerel; ag ya da root gerektirmez).

Neden var (dordü yerelde ÜRETILMIS gercek kusur):
1. pacman alan etiketlerini yerellestirir ("İsim"/"Sürüm" vs "Name"/"Version").
   Etiketleri Ingilizce eslestiren ayristiricilar TR yerelinde HICBIR sey
   bulamiyordu: `graph` kurulu bir pakette rc=1 "Could not build graph" verdi,
   `dep_resolver` sürümü hep 'unknown' donduruyordu. readelf'teki yerel
   hatasinin ayni sinifi.
2. core/completion.py komut listesini elle tutuyordu ve 9 üst-düzey komutu
   geride birakmisti -> tab tamamlamasi o komutlar icin calismiyordu.
3. rpm-to-deb girdiyi dogrulamiyordu: .deb verilince rc=0 "DEB paketi hazir"
   diyordu (hic dönüsmeyen bir dönüsmü bassrili sayiyordu).
4. `--offline` bayragi config.OFFLINE_MODE'U yaziyor ama HICBIR yer okumuyordu.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import config
from core.completion import COMMANDS, CONVERT_FLAGS
from core.security import c_locale_env

REPO = Path(__file__).resolve().parent.parent


# == 1) C-locale ortam yardimcisi =============================================================

def test_c_locale_env_kopyalar_ve_C_yapar():
    env = c_locale_env()
    assert env["LC_ALL"] == "C"
    assert env["LANG"] == "C"
    assert env is not os.environ  # orijinal ortam degistirilmez


def test_c_locale_env_bos_ortamda_da_calisir(monkeypatch):
    import core.security as SEC

    monkeypatch.setattr(SEC.os, "environ", {})
    assert c_locale_env()["LC_ALL"] == "C"


# == 2) pacman cagrileri C locale ile yapilmali ===============================================

def _kaydedici(kayit: list[dict], rc: int = 1):
    def sahte(cmd, *a, **k):
        kayit.append({"cmd": list(cmd), "env": k.get("env")})
        return subprocess.CompletedProcess(args=list(map(str, cmd)),
                                           returncode=rc, stdout="", stderr="")
    return sahte


def test_dep_graph_Qi_cagrisi_C_locale_kullanir(monkeypatch):
    import core.dep_graph as DG

    gorulen: list[dict] = []
    monkeypatch.setattr(DG, "safe_run", _kaydedici(gorulen))
    monkeypatch.setattr(DG.shutil, "which", lambda n: "/usr/bin/pacman")
    DG.build_dep_graph(Path("demo-1.0-1-x86_64.pkg.tar.zst"))
    qi = [g for g in gorulen if "-Qi" in g["cmd"]]
    assert qi, "pacman -Qi hic cagrilmadi"
    for g in qi:
        assert g["env"] and g["env"].get("LC_ALL") == "C", \
            "ayristirilan pacman cagrisi C locale zorlamiyor"


def test_dep_resolver_Si_cagrisi_C_locale_kullanir(monkeypatch):
    import core.dep_resolver as DR

    gorulen: list[dict] = []
    monkeypatch.setattr(DR, "safe_run", _kaydedici(gorulen, rc=0))
    monkeypatch.setattr(DR.shutil, "which", lambda n: "/usr/bin/pacman")
    ok, ver = DR._check_pacman("demo")
    assert gorulen and gorulen[0]["env"].get("LC_ALL") == "C"
    assert ok is True and ver == "unknown"   # rc=1 degil -> paket var, etiket yok


def test_dep_resolver_Qi_cagrisi_C_locale_kullanir(monkeypatch):
    import core.dep_resolver as DR

    gorulen: list[dict] = []
    monkeypatch.setattr(DR, "safe_run", _kaydedici(gorulen))
    monkeypatch.setattr(DR.shutil, "which", lambda n: "/usr/bin/pacman")
    DR._check_pacman_installed("demo")
    assert gorulen and gorulen[0]["env"].get("LC_ALL") == "C"


def test_localize_etiket_parseri_sagirdirir():
    """Neden C locale sart: yerellestirilmis etiketler startswith ile bulunmaz."""
    tr = "İsim  : 7zip\nSürüm : 26.04-1\n"
    en = "Name  : 7zip\nVersion: 26.04-1\n"
    assert not [ln for ln in tr.splitlines() if ln.startswith("Name")]
    assert [ln for ln in en.splitlines() if ln.startswith("Name")]


# == 3) completion listesi gercek parserla ayni olmali ========================================

def _parser_komutlari() -> list[str]:
    out = subprocess.run([sys.executable, "main.py", "--help"], cwd=REPO,
                         capture_output=True, text=True, check=False).stdout
    duz = " ".join(out.split())      # argparse secenekleri satirsonu ile boler
    # Kullanim satirindaki alt-komut grubu "{a,b,c} ..." bicimindedir; --lang
    # / --theme gibi baska secenek gruplarini yakalamamak icin "..." ile sabitlenir.
    m = re.search(r"\{([a-z0-9._-]+(?:,[a-z0-9._-]+)+)\}\s*\.\.\.", duz)
    assert m, "yardim ciktisinda alt-komut listesi bulunamadi"
    return m.group(1).split(",")


def test_completion_listesi_parser_ile_birebir_ayni():
    """Drift kilidi: elle tutulan liste 9 komutu geride birakmisti."""
    real = set(_parser_komutlari())
    assert set(COMMANDS) == real, (
        f"completion'da eksik: {sorted(real - set(COMMANDS))}; "
        f"completion'da fazla: {sorted(set(COMMANDS) - real)}")


def test_convert_bayraklari_parserda_da_var():
    out = subprocess.run([sys.executable, "main.py", "convert", "--help"],
                         cwd=REPO, capture_output=True, text=True,
                         check=False).stdout
    for flag in CONVERT_FLAGS:
        assert flag in out, f"{flag} completion'da var ama parserda yok"


# == 4) rpm-to-deb girdi dogrulamasi ==========================================================

def _rpm_yamlap(tmp_path: Path, gecerli: bool) -> Path:
    f = tmp_path / ("g.ecerli.rpm" if gecerli else "g.deb")
    f.write_bytes((b"\xed\xab\xee\xdb" if gecerli else b"!<arch>\n") + b"\x00" * 64)
    return f


def test_rpm_to_deb_gecerli_magic_kabul_eder(monkeypatch, tmp_path):
    import cli

    monkeypatch.setattr(cli, "discover_tools", lambda: config.ToolPaths())
    import core.rpm_to_deb_converter as RC

    monkeypatch.setattr(RC, "is_rpm_to_deb_available", lambda: True)
    monkeypatch.setattr(
        RC, "rpm_to_deb",
        lambda p, o: (True, "ok", Path(str(p) + ".deb")))
    f = _rpm_yamlap(tmp_path, True)
    rc = cli._cmd_rpm_to_deb(__import__("argparse").Namespace(
        rpm=str(f), output_dir=str(tmp_path)))
    assert rc == 0


def test_rpm_to_deb_deb_girdiyi_reddeder(monkeypatch, tmp_path, capsys):
    import argparse

    import cli
    import core.rpm_to_deb_converter as RC

    monkeypatch.setattr(RC, "is_rpm_to_deb_available", lambda: True)
    monkeypatch.setattr(RC, "rpm_to_deb",
                        lambda p, o: (_ for _ in ()).throw(
                            AssertionError("magic oncesi cagrilmamali")))
    f = _rpm_yamlap(tmp_path, False)
    rc = cli._cmd_rpm_to_deb(argparse.Namespace(rpm=str(f),
                                                output_dir=str(tmp_path)))
    assert rc == 1
    out = capsys.readouterr().out
    assert "RPM" in out and "g.deb" in out


def test_rpm_to_deb_eksik_dosya_rc1(monkeypatch, tmp_path):
    import argparse

    import cli
    import core.rpm_to_deb_converter as RC

    monkeypatch.setattr(RC, "is_rpm_to_deb_available", lambda: True)
    rc = cli._cmd_rpm_to_deb(argparse.Namespace(rpm=str(tmp_path / "yok.rpm"),
                                                output_dir=str(tmp_path)))
    assert rc == 1


# == 5) --offline artik gercekten engelliyor ==================================================

def test_offline_mode_indirmeyi_engeller(monkeypatch):
    from core.downloader import download_package

    monkeypatch.setattr(config, "OFFLINE_MODE", True)
    try:
        download_package("https://example.invalid/x.deb")
    except RuntimeError as exc:
        assert "offline" in str(exc).lower()
    else:
        raise AssertionError("offline modda indirme engellenmedi")


def test_offline_mode_kapaliyken_engellemez(monkeypatch):
    """Bayrak anlanmiyor degil; yalnızca acikken etkisi var."""
    from core.downloader import download_package

    monkeypatch.setattr(config, "OFFLINE_MODE", False)
    try:
        download_package("https://example.invalid/x.deb")
    except RuntimeError as exc:
        assert "offline" not in str(exc).lower(), \
            "offline kapaliyken offline hatasi verildi"
    except Exception as exc:  # noqa: BLE001 - ag/URI hatasi kabul, ONEM LI olan
        # "offline" hatasinin yanlislikla atilmamasi; bu dal testin amaci icin
        # basarili sayilir.
        assert "offline" not in str(exc).lower()


def test_offline_bayragi_config_uzerinde_yazilir():
    """main.py -> config.OFFLINE_MODE akisi: tek okuma noktasi downloader."""
    src = (REPO / "main.py").read_text(encoding="utf-8")
    assert "config.OFFLINE_MODE = True" in src
    dn = (REPO / "core/downloader.py").read_text(encoding="utf-8")
    assert "OFFLINE_MODE" in dn, "bayrak yine okunmaz oldu"
