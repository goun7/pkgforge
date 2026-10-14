"""Snapshot yol ayrimlari: root/hizli-yardimci, btrfs/zfs/none ve hata kodlari.

Modulun %86'si kapsaniyordu; kapsanmayan kisim tam da "snapshot alinamadi"
kararlarinin kullaniciya nasil yansidigi yerdi (yetki reddi, helper istisnasi,
ZFS dataset bulunamamasi). Snapshot, geri-alinabilirlik iddiasinin temeli oldugu
icin bu dallarin sessizce yanlis donmesi buyuk risk.

Hepsi monkeypatch ile: gerçek pkexec/btrfs/zfs cagrisi YOK, dis cagri YOK.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import core.snapshot_manager as SM
from core.snapshot_manager import SnapshotInfo, delete_snapshot, take_snapshot
from i18n import tr


def _tamam(kod: int = 0, out: str = "", hata: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["x"], returncode=kod, stdout=out, stderr=hata)


@pytest.fixture()
def etiket(monkeypatch: pytest.MonkeyPatch) -> str:
    ad = "pkgforge-20260101-000000-test"
    monkeypatch.setattr(SM, "snapshot_name", lambda label="pkgforge": ad)
    return ad


# --- root baglami: dogrudan calisma ------------------------------------------

@pytest.mark.parametrize("backend,ozel", [("btrfs", "_take_btrfs_snapshot"),
                                          ("zfs", "_take_zfs_snapshot")])
def test_root_backend_dogrudan_cagrilir(monkeypatch, etiket, backend, ozel):
    monkeypatch.setattr(SM, "detect_backend", lambda: backend)
    monkeypatch.setattr(SM.os, "geteuid", lambda: 0)
    beklenen = SnapshotInfo(backend=backend, snapshot_name=etiket, mount_point="/",
                            success=True, detail="ok")
    cagrildi = []

    def sahte(_ad):
        cagrildi.append(_ad)
        return beklenen

    monkeypatch.setattr(SM, ozel, sahte)
    sonuc = take_snapshot()
    assert cagrildi == [etiket]
    assert sonuc is beklenen


def test_root_backend_yoksa_bilgi_verir(monkeypatch, etiket):
    monkeypatch.setattr(SM, "detect_backend", lambda: "none")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 0)
    sonuc = take_snapshot()
    assert sonuc.success is False
    assert sonuc.detail == tr("snap.backend_algilanmadi")


# --- kullanici baglami: ayricalikli yardimci ----------------------------------

def test_kullanici_btrfs_helper_argv(monkeypatch, etiket):
    gorulen: list[list[str]] = []
    monkeypatch.setattr(SM, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, **kw: gorulen.append(list(cmd)) or _tamam())
    sonuc = take_snapshot()
    assert sonuc.success is True
    assert sonuc.detail == tr("snap.hazir_target", target=f"/{etiket}")
    assert "take-btrfs" in gorulen[0]
    assert gorulen[0][-1] == f"/{etiket}"


def test_kullanici_zfs_dataset_bulunamazsa(monkeypatch, etiket):
    monkeypatch.setattr(SM, "detect_backend", lambda: "zfs")
    monkeypatch.setattr(SM, "_get_zfs_root_dataset", lambda: "")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 1000)
    sonuc = take_snapshot()
    assert sonuc.success is False
    assert sonuc.backend == "zfs"
    assert sonuc.detail == tr("snap.zfs_root_bulunamadi")


def test_kullanici_zfs_dataset_ile(monkeypatch, etiket):
    gorulen: list[list[str]] = []
    monkeypatch.setattr(SM, "detect_backend", lambda: "zfs")
    monkeypatch.setattr(SM, "_get_zfs_root_dataset", lambda: "pool/ROOT")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, **kw: gorulen.append(list(cmd)) or _tamam())
    sonuc = take_snapshot()
    assert sonuc.success is True
    assert gorulen[0][-1] == f"pool/ROOT@{etiket}"


def test_kullanici_backend_yok(monkeypatch, etiket):
    monkeypatch.setattr(SM, "detect_backend", lambda: "none")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 1000)
    sonuc = take_snapshot()
    assert sonuc.success is False and sonuc.detail == tr("snap.backend_algilanmadi")


def test_helper_istisna_firlatirsa(monkeypatch, etiket):
    monkeypatch.setattr(SM, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 1000)

    def patla(_cmd, **_kw):
        raise OSError("pkexec crashed")

    monkeypatch.setattr(SM, "safe_run", patla)
    sonuc = take_snapshot()
    assert sonuc.success is False
    assert "pkexec crashed" in sonuc.detail


@pytest.mark.parametrize("kod,beklenen", [
    (126, tr("snap.yetki_reddedildi")),
    (127, tr("snap.yetki_reddedildi")),
    (1, "subvolume create: permission denied"),
    (2, tr("snap.basarisiz_kod", kod=2)),
])
def test_kod_yol_ayrimlari(monkeypatch, etiket, kod, beklenen):
    monkeypatch.setattr(SM, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 1000)
    hata = "subvolume create: permission denied" if kod == 1 else ""
    monkeypatch.setattr(SM, "safe_run",
                        lambda _cmd, **_kw: _tamam(kod=kod, hata=hata))
    sonuc = take_snapshot()
    assert sonuc.success is False
    assert sonuc.detail == beklenen


# --- silme yollari ------------------------------------------------------------

def test_silme_oneksiz_adi_reddeder(monkeypatch):
    cagrildi = []
    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, **kw: cagrildi.append(cmd) or _tamam())
    # '@' sonrasi gelen etiket 'pkgforge-' ile baslamali; aksi halde hicbir
    # disari cagri yapilmadan reddedilir (rastgele snapshot'i silme riski).
    assert delete_snapshot("pool/ROOT@haric") is False
    assert cagrildi == []          # hic bir sey silinmedi


def test_silme_root_zfs(monkeypatch):
    gorulen: list[list[str]] = []
    monkeypatch.setattr(SM, "detect_backend", lambda: "zfs")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 0)
    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, **kw: gorulen.append(list(cmd)) or _tamam())
    assert delete_snapshot("pool/ROOT@pkgforge-x") is True
    assert gorulen[0][:2] == ["zfs", "destroy"]


def test_silme_root_bilinmeyen_backend(monkeypatch):
    monkeypatch.setattr(SM, "detect_backend", lambda: "lvm")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 0)
    assert delete_snapshot("@pkgforge-x") is False


def test_silme_kullanici_backend_yok(monkeypatch):
    monkeypatch.setattr(SM, "detect_backend", lambda: "none")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 1000)
    assert delete_snapshot("@pkgforge-x") is False


def test_silme_kullanici_helper_istisnasi(monkeypatch):
    monkeypatch.setattr(SM, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 1000)

    def patla(_cmd, **_kw):
        raise RuntimeError("yetki verilmedi")

    monkeypatch.setattr(SM, "safe_run", patla)
    assert delete_snapshot("@pkgforge-x") is False


def test_silme_kullanici_basarisiz_kod(monkeypatch):
    monkeypatch.setattr(SM, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(SM.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(SM, "safe_run", lambda _c, **_k: _tamam(kod=1))
    assert delete_snapshot("@pkgforge-x") is False


# --- pathguard: isletim sistemi hatalari yukseltilmez -------------------------

def test_pathguard_oserror_dallari(monkeypatch: pytest.MonkeyPatch) -> None:
    from core import pathguard

    def oserror(_self):
        raise OSError(21, "Is a directory")

    monkeypatch.setattr(Path, "is_file", oserror)
    monkeypatch.setattr(Path, "exists", oserror)
    assert pathguard.is_file_safe("/x") is False
    assert pathguard.exists_safe("/x") is False


def test_pathguard_realpath_basarisizsa_soze_sah_duser(monkeypatch) -> None:
    from core import pathguard

    def patla(_p, **_kw):
        raise OSError(40, "Too many levels of symbolic links")

    monkeypatch.setattr(pathguard.os.path, "realpath", patla)
    cozum = pathguard.guarded_path("/tmp/../tmp/x", field="pkg_path")
    assert str(cozum) == "/tmp/x"
