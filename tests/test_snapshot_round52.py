"""Tur-52 — snapshot_manager tam kapsama (test-only, urun dosyasina dokunulmaz)."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.snapshot_manager as SM

OK = NS(returncode=0, stdout="", stderr=b"")


def _sahte_mounts(monkeypatch, satirlar, hata=False):
    import builtins

    gercek_open = builtins.open

    def sahte_open(dosya, *a, **k):
        if str(dosya) == "/proc/mounts":
            if hata:
                raise OSError("okunamadi")
            from io import StringIO
            return StringIO("\n".join(satirlar))
        return gercek_open(dosya, *a, **k)

    monkeypatch.setattr(builtins, "open", sahte_open)


# ── 62-72: get_root_mount_point ──────────────────────────────────────────────────

def test_root_mount_point_found(monkeypatch):
    _sahte_mounts(monkeypatch, [
        "sysfs /sys sysfs rw 0 0",
        "/dev/nvme0n1p2 / btrfs rw,subvol=/@ 0 0",
        "/dev/sda1 /home ext4 rw 0 0",
    ])
    assert SM.get_root_mount_point() == "/dev/nvme0n1p2"          # 68-69


def test_root_mount_point_missing_and_error(monkeypatch):
    _sahte_mounts(monkeypatch, ["sysfs /sys sysfs rw 0 0"])
    assert SM.get_root_mount_point() == ""                        # 72

    _sahte_mounts(monkeypatch, [], hata=True)
    assert SM.get_root_mount_point() == ""                        # 70-71


# ── dispatch dallari: 88-91 / 116-121 / 130-135 / 140-147 ────────────────────────

def test_take_restore_list_delete_dispatch(monkeypatch):
    cagrilan = []
    monkeypatch.setattr(SM, "_take_snapshot_privileged",
                        lambda be, ad: cagrilan.append(("priv", be, ad))
                        or SM.SnapshotInfo(be, ad, "/", True, ""))
    monkeypatch.setattr(SM, "_restore_btrfs_snapshot",
                        lambda ad: cagrilan.append(("br", ad)) or (True, ""))
    monkeypatch.setattr(SM, "_restore_zfs_snapshot",
                        lambda ad: cagrilan.append(("zr", ad)) or (True, ""))
    monkeypatch.setattr(SM, "_list_btrfs_snapshots",
                        lambda: cagrilan.append(("bl",)) or [])
    monkeypatch.setattr(SM, "_list_zfs_snapshots",
                        lambda: cagrilan.append(("zl",)) or [])

    durum = {"d": ""}
    monkeypatch.setattr(SM, "detect_backend", lambda: durum["d"])

    durum["d"] = "btrfs"
    SM.take_snapshot("x")
    SM.restore_snapshot("/pkgforge-x")
    SM.list_snapshots()

    durum["d"] = "zfs"
    SM.take_snapshot("y")
    SM.restore_snapshot("zroot@pkgforge-y")
    SM.list_snapshots()

    # delete: helper tek-diyalog sozlesmesi (pkexec snapshot ...)
    silinen = []
    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, timeout=0:
                        silinen.append(cmd) or OK)
    durum["d"] = "btrfs"
    assert SM.delete_snapshot("/pkgforge-x") is True
    assert silinen[0][0] == "pkexec" and "delete-btrfs" in silinen[0]
    durum["d"] = "zfs"
    assert SM.delete_snapshot("zroot@pkgforge-p") is True
    assert "destroy-zfs" in silinen[-1]
    durum["d"] = ""
    assert SM.delete_snapshot("x") is False
    # oneksiz ad reddedilir
    assert SM.delete_snapshot("/x") is False

    tur = [c[0] for c in cagrilan]
    assert tur == ["priv", "br", "bl", "priv", "zr", "zl"]


def test_take_snapshot_none_backend(monkeypatch):
    monkey = None
    assert SM.take_snapshot.__doc__
    # Backend yok: helper'a da gidilmez, parola sorulmaz.
    monkeypatch.setattr(SM, "detect_backend", lambda: "none")
    bilgi = SM.take_snapshot("n")
    assert bilgi.backend == "none" and bilgi.success is False
    del monkey


# ── 152-166: btrfs kok subvolume ─────────────────────────────────────────────────

def test_btrfs_root_subvolume(monkeypatch):
    _sahte_mounts(monkeypatch, [
        "/dev/sda2 / btrfs rw,ssd,subvol=/@pkgforge-ana 0 0",
    ])
    assert SM._get_btrfs_root_subvolume() == "/@pkgforge-ana"       # 158-163

    _sahte_mounts(monkeypatch, ["/dev/sda2 / ext4 rw 0 0"])
    assert SM._get_btrfs_root_subvolume() == "@"                    # 164-166

    _sahte_mounts(monkeypatch, [], hata=True)
    assert SM._get_btrfs_root_subvolume() == "@"


# ── 178-195: btrfs snapshot basari/basarisizlik ──────────────────────────────────

def test_take_btrfs_success_and_fail(monkeypatch):
    monkeypatch.setattr(SM, "safe_run", lambda cmd, timeout=0: OK)
    iyi = SM._take_btrfs_snapshot("pkgforge-t1")                    # 178-186
    assert iyi.success is True and iyi.snapshot_name == "/pkgforge-t1"

    monkeypatch.setattr(
        SM, "safe_run",
        lambda cmd, timeout=0:
        NS(returncode=1, stderr=b"kopyalama hatasi"))
    kotu = SM._take_btrfs_snapshot("pkgforge-t2")                   # 187-189
    assert kotu.success is False and "başarısız" in kotu.detail


# ── 226-288: btrfs geri yukleme plani (yol-lar tmp'ye yonlendirilir) ─────────────

@pytest.fixture()
def izole_yollar(tmp_path, monkeypatch):
    bin_dir = tmp_path / "usr-local-bin"
    etc_dir = tmp_path / "etc-systemd"
    bin_dir.mkdir()
    etc_dir.mkdir()

    class SahtePath(Path):
        pass

    def sahte_path(hedef, *a, **k):
        hedef_str = str(hedef)
        if hedef_str.startswith("/usr/local/bin"):
            return Path(bin_dir) / Path(hedef_str).name
        if hedef_str.startswith("/etc/systemd"):
            return Path(etc_dir) / Path(hedef_str).name
        return Path(hedef_str)

    monkeypatch.setattr(SM, "Path", sahte_path)
    return {"bin": bin_dir, "etc": etc_dir, "kok": tmp_path}


def test_restore_btrfs_pkexec_fail_fallback(monkeypatch, izole_yollar):
    """257-273: pkexec basarisiz -> /tmp devir dosyasi mesaji."""
    arka = []

    def sahte_safe_run(cmd, timeout=0, input=None, **k):
        arka.append((cmd, bool(input)))
        return NS(returncode=1, stderr=b"polkit reddi")

    monkeypatch.setattr(SM, "safe_run", sahte_safe_run)
    eski_pid = os.getpid
    monkeypatch.setattr(os, "getpid", lambda: 24680)
    ok, msg = SM._restore_btrfs_snapshot("pkgforge-s1")             # 226-273
    monkeypatch.setattr(os, "getpid", eski_pid)
    assert ok is True and "sudo cp" in msg and "pkgforge-rollback-24680" in msg
    # devir dosyasi temizligi
    tmp_dosya = Path("/tmp/pkgforge-rollback-24680.service")
    tmp_dosya.unlink(missing_ok=True)


def test_restore_btrfs_pkexec_ok(monkeypatch, izole_yollar):
    komutlar = []

    def sahte_safe_run(cmd, timeout=0, input=None, **k):
        komutlar.append((cmd, bool(input)))
        return NS(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(SM, "safe_run", sahte_safe_run)
    ok, msg = SM._restore_btrfs_snapshot("/pkgforge-s2")
    assert ok is True and "yeniden başlattığınızda" in msg
    # TEK diyalog: service-deploy (manifest + unit).
    assert len(komutlar) == 1
    cmd, _vardata = komutlar[0]
    assert "service-deploy" in cmd and "pkgforge-rollback.service" in cmd


def test_restore_btrfs_script_write_oserror(monkeypatch, izole_yollar):
    def patlak(cmd, timeout=0, input=None, **k):
        raise OSError("disk salt-okunur")

    monkeypatch.setattr(SM, "safe_run", patlak)
    ok, msg = SM._restore_btrfs_snapshot("pkgforge-s3")
    assert ok is False and "oluşturulamadı" in msg


def test_restore_btrfs_unexpected_exception(monkeypatch, izole_yollar):
    """Servis asamasinda beklenmeyen istisna → False + aciklama."""

    def patlak(cmd, timeout=0, input=None, **k):
        raise RuntimeError("yetki servisi koptu")

    monkeypatch.setattr(SM, "safe_run", patlak)
    ok, msg = SM._restore_btrfs_snapshot("pkgforge-s4")
    assert ok is False and "Rollback planı oluşturulamadı" in msg


# ── 291-310: btrfs liste ─────────────────────────────────────────────────────────

def test_list_btrfs_snapshots_parse_and_error(monkeypatch):
    cikti = (
        "ID 256 gen 100 cgen 100 parent 5 top level 5 otime"
        " 2026-01-01 10:00:00 path @\n"
        "ID 300 gen 120 cgen 120 parent 5 top level 5 otime"
        " 2026-06-01 11:30:00 path pkgforge-demo-111\n"
        "ID 301 gen 121 cgen 121 parent 5 top level 5 otime"
        " 2026-06-02 09:15:00 path baska-222\n"
    )
    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=0, stdout=cikti, stderr=b""))
    liste = SM._list_btrfs_snapshots()                              # 297-307
    assert len(liste) == 1
    assert liste[0]["name"] == "/pkgforge-demo-111"
    assert liste[0]["backend"] == "btrfs"
    assert liste[0]["date"] == "cgen 120 parent 5"

    def patlak(cmd, timeout=0):
        raise RuntimeError("altistem kaldi")
    monkeypatch.setattr(SM, "safe_run", patlak)
    assert SM._list_btrfs_snapshots() == []                         # 308-309


# ── ZFS: 315-383 ─────────────────────────────────────────────────────────────────

def test_zfs_dataset_lookup(monkeypatch):
    cikti = "zroot/ROOT/default\t/\nzroot/home\t/home"
    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=0, stdout=cikti, stderr=b""))
    assert SM._get_zfs_root_dataset() == "zroot/ROOT/default"       # 321-325

    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=1, stdout="", stderr=b"yok"))
    assert SM._get_zfs_root_dataset() == ""                          # 326


def test_zfs_take_paths(monkeypatch):
    monkeypatch.setattr(SM, "_get_zfs_root_dataset",
                        lambda: "zroot/ROOT/default")

    monkeypatch.setattr(SM, "safe_run", lambda cmd, timeout=0: OK)
    iyi = SM._take_zfs_snapshot("pkgforge-z1")                      # 338-349
    assert iyi.success and iyi.snapshot_name ==         "zroot/ROOT/default@pkgforge-z1"

    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=1, stdout="", stderr=b"busy"))
    kotu = SM._take_zfs_snapshot("pkgforge-z2")                     # 350-354
    assert not kotu.success and "başarısız" in kotu.detail


def test_zfs_take_no_dataset(monkeypatch):
    monkeypatch.setattr(SM, "_get_zfs_root_dataset", lambda: "")
    bilgi = SM._take_zfs_snapshot("pkgforge-z3")                    # 332-336
    assert not bilgi.success and "bulunamadı" in bilgi.detail


def test_restore_zfs_message():
    ok, msg = SM._restore_zfs_snapshot("zroot@pkgforge-z9")         # 357-366
    assert ok is True and "zfs rollback zroot@pkgforge-z9" in msg


def test_list_zfs_no_dataset(monkeypatch):
    monkeypatch.setattr(SM, "_get_zfs_root_dataset", lambda: "")
    assert SM._list_zfs_snapshots() == []                            # 372-374


# ── detect_backend yollari ve zfs liste parcasi ─────────────────────────────

def test_detect_backend_paths(monkeypatch):
    import shutil as shutil_mod
    monkeypatch.setattr(shutil_mod, "which", lambda n: None)
    assert SM.detect_backend() == "none"                            # 59

    # btrfs dogrulandi
    monkeypatch.setattr(shutil_mod, "which",
                        lambda n: "/usr/bin/" + n if n in ("btrfs", "zfs") else None)
    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=0, stdout="Label: none uuid: ... btrfs", stderr=b""))
    assert SM.detect_backend() == "btrfs"                          # 50-51

    # btrfs reddi -> zfs bulundu
    def secici(cmd, timeout=0):
        if cmd[0] == "btrfs":
            return NS(returncode=1, stdout=b"", stderr=b"")
        return NS(returncode=0, stdout="zroot/ROOT/default	/", stderr=b"")
    monkeypatch.setattr(SM, "safe_run", secici)
    assert SM.detect_backend() == "zfs"                            # 55-57

    # ikisi de reddedildi -> none
    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=1, stdout=b"", stderr=b""))
    assert SM.detect_backend() == "none"


def test_restore_and_list_none_backend(monkeypatch):
    monkeypatch.setattr(SM, "detect_backend", lambda: "")
    assert SM.restore_snapshot("x") == (False, "Btrfs veya ZFS algılanamadı")  # 120-121
    assert SM.list_snapshots() == []                                # 135


def test_list_zfs_parse(monkeypatch):
    monkeypatch.setattr(SM, "_get_zfs_root_dataset",
                        lambda: "zroot/ROOT/default")
    cikti = ("zroot/ROOT/default@pkgforge-z1\tMon Jan  1 10:00:00 2026\n"
             "zroot/ROOT/default@pkgforge-z2\tTue Jan  2 11:00:00 2026\n")
    monkeypatch.setattr(SM, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=0, stdout=cikti, stderr=b""))
    liste = SM._list_zfs_snapshots()                                # 381-389
    assert [k["name"] for k in liste] == [
        "zroot/ROOT/default@pkgforge-z1",
        "zroot/ROOT/default@pkgforge-z2",
    ]
    assert all(k["backend"] == "zfs" for k in liste)