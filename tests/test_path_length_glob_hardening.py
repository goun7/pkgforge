"""Uzun yol girdisi ve glob-enjeksiyonu sertlestirmesi (CI'de bulunan gercek hata).

Iki olcumus hata:

1) `Path.is_file()` Python <=3.12'de ENAMETOOLONG'u YUKSELIYOR (3.13/3.14 False
   doner). Kullanici/RPC kaynakli 255+ baytlik bir ad, `pkgforge graph` ve
   tools handler'larinda yakalanmamis OSError -> traceback uretiyordu. CI
   3.10-3.14 kosularinda goruldu; yerel 3.14'te gorunmuyordu.
2) Pacman cache taramasi kullanici adini glob DESENINE gor gomuyordu:
   `pkgforge graph "*"` veya `""` cache'ten rastgele bir paketi secip ONU
   analiz ediyordu — yani kullaniciya ait olmayan bir hedef uzerinde calisma.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, ".")

import cli
from core.pathguard import (
    PathNotAllowed,
    ad_cok_uzun,
    exists_safe,
    guarded_path,
    is_file_safe,
)

UZUN_AD = "a" * 500


# --- 1) uzun ad: patlamaz, "yok" der ------------------------------------------

def test_uzun_ad_is_file_safe_patlatmaz() -> None:
    assert is_file_safe(UZUN_AD) is False
    assert is_file_safe(Path("/tmp") / UZUN_AD) is False


def test_uzun_ad_exists_safe_patlatmaz() -> None:
    assert exists_safe(UZUN_AD) is False


def test_ad_cok_uzun_olcu() -> None:
    assert ad_cok_uzun(UZUN_AD) is True
    assert ad_cok_uzun("/tmp/x.pkg.tar.zst") is False
    # bilesenler kisa ama toplam yol PATH_MAX'i asiyor
    assert ad_cok_uzun("/".join(["abcde"] * 1200)) is True


def test_guarded_path_uzun_girdiyi_geri_cevirir() -> None:
    with pytest.raises(PathNotAllowed) as ei:
        guarded_path(UZUN_AD, field="pkg_path")
    assert "pkg_path" in str(ei.value)


def test_graph_komutu_uzun_adla_traceback_vermez(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli._cmd_graph(NS(package=UZUN_AD, files=False, format="ascii"))
    cikti = capsys.readouterr().out
    assert rc == 1
    assert "Traceback" not in cikti


# --- 2) glob enjeksiyonu ------------------------------------------------------

def test_bos_ad_cache_taramasina_girmez(monkeypatch: pytest.MonkeyPatch) -> None:
    cagrilan: list[str] = []
    import glob as globmod

    monkeypatch.setattr(globmod, "glob",
                        lambda p: (cagrilan.append(p), [])[1])
    assert cli._resolve_pkg_file("") is None
    assert cli._resolve_pkg_file("   ") is None
    assert cagrilan == []


def test_glob_meta_karakterler_desen_olamaz(monkeypatch: pytest.MonkeyPatch) -> None:
    cagrilan: list[str] = []
    import glob as globmod

    monkeypatch.setattr(globmod, "glob",
                        lambda p: (cagrilan.append(p), [])[1])
    assert cli._resolve_pkg_file("*") is None
    assert len(cagrilan) == 2
    for desen in cagrilan:
        # yildiz karakterle eslesme yapilamaz; sadece ek kismi serbest
        assert "[*]" in desen, desen
        assert not desen.endswith("/*.pkg.tar.zst"), desen


def test_gercek_dosya_yolu_cozulur(tmp_path: Path) -> None:
    hedef = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    hedef.write_bytes(b"x")
    assert cli._resolve_pkg_file(str(hedef)) == hedef


def test_cache_adi_cozulur(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import glob as globmod

    bulunan = tmp_path / "krb5-1.22.2-1-x86_64.pkg.tar.zst"
    bulunan.write_bytes(b"x")
    monkeypatch.setattr(globmod, "glob", lambda _p: [str(bulunan)])
    assert cli._resolve_pkg_file("krb5") == bulunan
