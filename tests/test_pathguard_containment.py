"""core/pathguard — RPC/HTTP dosya yolu containment testi.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi (asistan
         dosyalari hariç; onlar üretim düzeltmesinin parçasi).
Kural-4: saf in-memory — dis komut/ag YOK; symlink ve dosyalar tmp_path'te.

Neden var: sidecar dosya-yolu parametrelerini yalnizca is_file() ile
dogruluyordu. Kanitlanmis sizarma (alt-ajan üretti):
  security.verify pkg_path=/etc/shadow  -> kabul
  system.open_path path=/etc/passwd     -> gercekten xdg-open /etc cagrildi
  queue.add paths=["/etc/passwd"]       -> kuyruga kaydedildi
  install.rehearse package_path=/etc    -> host /etc konteynere ro bind-mount
Bir paket kurma aracinin yerel soketi, yol parametresini keyfi host erisimine
cevirme noktasi olmamali.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.pathguard import (
    ALLOWED_UNDER_DENY,
    DENIED_HOME_SUBPATHS,
    DENIED_ROOTS,
    PathNotAllowed,
    guarded_path,
    guarded_paths,
)

HOSTALE = [
    "/etc/shadow",
    "/etc/passwd",
    "/etc/ld.so.preload",
    "/usr/bin/pacman",
    "/usr/lib/systemd/system/dbus.socket",
    "/bin/sh",
    "/sbin/init",
    "/boot/vmlinuz-linux",
    "/proc/self/environ",
    "/sys/power/state",
    "/dev/mem",
    "/root/.ssh/authorized_keys",
    "/var/lib/pacman/db.lck",
    "/run/user/1000/bus",
]


# == reddilen sistem yollari ====================================================================

@pytest.mark.parametrize("yol", HOSTALE)
def test_sistem_yollari_reddedilir(yol):
    with pytest.raises(PathNotAllowed):
        guarded_path(yol, field="pkg_path")


def test_bos_ve_sade_bosluk_reddedilir():
    for deger in ("", "   ", None):
        with pytest.raises(PathNotAllowed):
            guarded_path(deger, field="p")


def test_kullanicinin_kendi_kredi_dizinleri_reddedilir():
    home = Path(os.path.expanduser("~"))
    for alt in DENIED_HOME_SUBPATHS:
        with pytest.raises(PathNotAllowed):
            guarded_path(home / alt / "id_rsa", field="p")


def test_root_home_reddedilir(tmp_path, monkeypatch):
    """Kullanici kendi home'unda serbest; /root ise her zaman kapali."""
    monkeypatch.setenv("HOME", str(tmp_path / "ben"))
    (tmp_path / "ben").mkdir()
    with pytest.raises(PathNotAllowed):
        guarded_path("/root/.ssh/id_rsa", field="p")


def test_varolmayan_sistem_yolu_da_reddedilir():
    """is_file() kontrolunden ONCE reddedilir -> var/yok bilgisi sizintisi yok."""
    with pytest.raises(PathNotAllowed):
        guarded_path("/etc/böyle-bir-dosya-yok", field="p")


# == meşru kullanim ============================================================================

def test_tmp_ve_home_mesru(tmp_path):
    f = tmp_path / "paket.pkg.tar.zst"
    f.write_bytes(b"P")
    assert guarded_path(f, field="p") == Path(os.path.realpath(f))


def test_pacman_cache_mesru():
    """/var genelde reddedilir; pacman cache istisnasi calismayi sürdürmeli."""
    got = guarded_path("/var/cache/pacman/pkg/demo-1-1-x86_64.pkg.tar.zst")
    assert str(got).startswith("/var/cache/pacman")
    assert "/var/cache/pacman" in ALLOWED_UNDER_DENY


def test_var_tmp_mesru():
    assert str(guarded_path("/var/tmp/cikti.deb")).startswith("/var/tmp")


def test_cikti_dizini_olarak_bos_olmayan_home_mesru(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    hedef = tmp_path / "Downloads" / "paket.pkg.tar.zst"
    assert guarded_path(hedef) == Path(os.path.realpath(hedef))


# == symlink kacagi ============================================================================

def test_izinli_symlink_kacagi_reddedilir(tmp_path):
    """Izinli dizindeki bir symlink reddedilen hedefi gösteriyorsa geçit yok."""
    hedef_dizin = tmp_path / "izinli"
    hedef_dizin.mkdir()
    link = hedef_dizin / "masum.pkg.tar.zst"
    link.symlink_to("/etc/shadow")
    with pytest.raises(PathNotAllowed):
        guarded_path(link, field="p")


def test_izinli_dizine_giden_symlink_kabul(tmp_path):
    d = tmp_path / "a"
    d.mkdir()
    gercek = tmp_path / "b"
    gercek.mkdir()
    dosya = gercek / "p.deb"
    dosya.write_bytes(b"x")
    link = d / "p.deb"
    link.symlink_to(dosya)
    assert guarded_path(link) == dosya.resolve()


# == guarded_paths ==============================================================================

def test_guarded_paths_hepsini_denetler(tmp_path):
    iyi = tmp_path / "iyi.deb"
    iyi.write_bytes(b"x")
    sonuc = guarded_paths([str(iyi)], field="paths")
    assert len(sonuc) == 1


def test_guarded_paths_bos_liste_reddedilir():
    with pytest.raises(PathNotAllowed):
        guarded_paths([], field="paths")
    with pytest.raises(PathNotAllowed):
        guarded_paths(None, field="paths")


def test_guarded_paths_tek_kotu_butun_listeyi_dusurur(tmp_path):
    iyi = tmp_path / "iyi.deb"
    iyi.write_bytes(b"x")
    with pytest.raises(PathNotAllowed):
        guarded_paths([str(iyi), "/etc/shadow"], field="paths")


def test_hata_mesajinda_alan_adi_var():
    with pytest.raises(PathNotAllowed) as ei:
        guarded_path("/etc/shadow", field="backup_path")
    assert "backup_path" in str(ei.value)


def test_path_not_allowed_valueerror_ailesinde():
    """Eski cagiranlar except ValueError ile henuz yakalar -> kirilma yok."""
    assert issubclass(PathNotAllowed, ValueError)


# == handler entegrasyonu ======================================================================

def test_require_pkg_file_sistem_yolunu_reddediyor():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import core.api.transport as TR

    with pytest.raises(PathNotAllowed):
        TR._require_pkg_file({"pkg_path": "/etc/shadow"})


def test_open_path_handler_sistem_yolunu_reddediyor():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import core.api.handlers_system as HS

    with pytest.raises(PathNotAllowed):
        HS.handle_system_open_path({"path": "/etc/passwd"})


def test_queue_add_handler_sistem_yolunu_reddediyor():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import core.api.handlers_queue as HQ

    with pytest.raises(PathNotAllowed):
        HQ.handle_queue_add({"paths": ["/etc/passwd"]})


def test_denied_roots_listi_kapsamli():
    for beklenen in ("/etc", "/usr", "/root", "/proc", "/sys", "/dev", "/boot"):
        assert beklenen in DENIED_ROOTS


# == POLICY DOCSTRING (bilincli sinir) =========================================================

def test_tmp_alti_mesru_oldugu_icin_acik_birakildigi_belgeli():
    """CSP/convert akislari /tmp'a yazar -> /tmp reddedileMEZ (tasarim geregi).

    Bu test, politikanin kasitli sinirini sabitler; biri /tmp'i sansurlerse
    donusum hatti kirilir ve test bunu hemen gorur.
    """
    assert "/tmp" not in DENIED_ROOTS
    assert str(guarded_path("/tmp/bir-dosya.deb")).startswith("/tmp")
