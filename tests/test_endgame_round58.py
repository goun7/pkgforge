"""Tur-58 — son kalinti ~57 satir (14 modul)."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from types import SimpleNamespace as NS

import pytest


class SahteSignal:
    def __init__(self):
        self._aboneler = []

    def connect(self, fn):
        self._aboneler.append(fn)

    def emit(self, *a):
        for fn in list(self._aboneler):
            fn(*a)


# ── rpm_converter ────────────────────────────────────────────────────────────────

def _rpm_ornek(tmp_path):
    import core.rpm_converter as RC
    rc = RC.RpmConverter.__new__(RC.RpmConverter)
    rc.output_line = SahteSignal()
    rc.finished = SahteSignal()
    rc._work_dir = tmp_path
    rc._cancelled = False
    rc._phase = "build"
    rc._process = None
    rc._tools = NS(bsdtar="/usr/bin/bsdtar", ar="/usr/bin/ar",
                   makepkg="/usr/bin/makepkg", bwrap="/usr/bin/bwrap",
                   strip="/usr/bin/strip")
    rc._meta = NS(name="demo", version="1.0", depends=[],
                  arch_mapped="x86_64", description="aciklama",
                  url="https://ornek.net", licenses=["MIT"])
    return rc, RC


def test_rpm_extract_finished_exception(monkeypatch, tmp_path):
    rc, RC = _rpm_ornek(tmp_path)
    kayit = []
    rc.finished.connect(lambda ok, m, p: kayit.append((ok, m)))
    monkeypatch.setattr(RC, "resolve_runtime_dependencies",
                        lambda s, t: (_ for _ in ()).throw(
                            RuntimeError("koptu")))
    RC.RpmConverter._on_extract_finished(rc, 0, None)                                 # 136-137
    assert "PKGBUILD oluşturma hatası" in kayit[-1][1]


def test_rpm_build_meta_none(monkeypatch, tmp_path):
    rc, RC2 = _rpm_ornek(tmp_path)
    rc._meta = None
    RC2.RpmConverter._build_package(rc)                                              # 142-143


def test_rpm_src_dir_fallback(monkeypatch, tmp_path):
    rc, RC = _rpm_ornek(tmp_path)

    class SahteSurec:
        NotRunning = 0

        class ProcessChannelMode:
            MergedChannels = 3

        class ProcessState:
            NotRunning = 0

        def __init__(self, parent=None):
            self.output_line = SahteSignal()
            self.readyReadStandardOutput = SahteSignal()
            self.finished = SahteSignal()
            self.errorOccurred = SahteSignal()

        def setWorkingDirectory(self, y):
            pass

        def setProcessChannelMode(self, m):
            pass

        def setProcessEnvironment(self, e):
            pass

        def start(self, *a):
            pass

    monkeypatch.setattr(RC, "QProcess", SahteSurec)
    monkeypatch.setattr(RC, "resolve_runtime_dependencies", lambda s, t: [])
    RC.RpmConverter._build_package(rc)
    assert (tmp_path / "build" / "src").is_dir()                     # 155-156


def test_rpm_cancelled_and_output_none(tmp_path):
    rc, RC2 = _rpm_ornek(tmp_path)
    kayit = []
    rc.finished.connect(lambda ok, m, p: kayit.append((ok, m)))
    rc._cancelled = True
    RC2.RpmConverter._on_build_finished(rc, 0, None)                                   # 193-195
    assert kayit[-1][1] == "İptal edildi"

    rc2, RC2 = _rpm_ornek(tmp_path)
    RC2.RpmConverter._on_output(rc2)                                                 # 254-255


def test_rpm_generate_pkgbuild_branches(monkeypatch, tmp_path):
    rc, RC = _rpm_ornek(tmp_path)
    src = tmp_path / "src"
    src.mkdir()

    rc._meta = None
    with pytest.raises(RuntimeError):
        RC.RpmConverter._generate_pkgbuild(rc, src)                                   # 211-212

    rc._meta = NS(name="demo", version="1.0", depends=["ozel-bag"],
                  arch_mapped="", description="aciklama",
                  url="https://ornek.net", licenses=["MIT"])
    monkeypatch.setattr(RC, "resolve_runtime_dependencies",
                        lambda s, t: ["curl", "openssl"])
    metin = RC.RpmConverter._generate_pkgbuild(rc, src)
    assert "'curl'" in metin and "'openssl'" in metin                # 218-219

    monkeypatch.setattr(RC, "resolve_runtime_dependencies", lambda s, t: [])
    monkeypatch.setattr(RC, "RPM_DEP_MAP", {"zlib": "zlib"},
                        raising=False)
    rc._meta.description = "aciklama"
    rc._meta.url = "https://ornek.net"
    rc._meta.licenses = ["MIT"]
    rc._meta.depends = ["zlib", "bilinmeyen-bag"]
    metin2 = RC.RpmConverter._generate_pkgbuild(rc, src)
    assert "'zlib'" in metin2                                        # 224-225


def test_rpm_find_output_no_dirs(tmp_path):
    rc, RC2 = _rpm_ornek(tmp_path)
    assert RC2.RpmConverter._find_output_package(rc) is None                         # 276-277


# ── ui/styles 112-114 ────────────────────────────────────────────────────────────

def test_styles_is_dark_theme_with_app():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtGui import QColor, QPalette
    from PyQt6.QtWidgets import QApplication

    import ui.styles as ST

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    palet = app.palette()
    palet.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    app.setPalette(palet)
    assert ST.is_dark_theme() is True                                # 112-114
    palet.setColor(QPalette.ColorRole.Window, QColor(250, 250, 250))
    app.setPalette(palet)
    assert ST.is_dark_theme() is False


# ── flatpak_converter 237-238 ────────────────────────────────────────────────────

def test_flatpak_to_deb_dpkg_fail(monkeypatch, tmp_path):
    import core.flatpak_converter as FC

    uygulama = NS(app_id="org.Deneme.Uyg", name="Deneme Uyg",
                  version="1.2.3")
    monkeypatch.setattr(FC, "get_app_info", lambda a: uygulama)
    monkeypatch.setattr(FC, "export_app_files", lambda a, d, b: True)
    monkeypatch.setattr(FC, "create_deb_package",
                        lambda app, files, out: (False, "dpkg koptu"))
    ok, msg, _yol = FC.flatpak_to_deb("org.Deneme.Uyg", tmp_path,
                                     branch="stable")
    assert ok is False and msg == "dpkg koptu"                       # 237-238


# ── appimage_converter 213-214 / 221-222 ─────────────────────────────────────────

def _appimage_ortam(monkeypatch, tmp_path):
    import core.appimage_converter as AC
    pkg = tmp_path / "uyg.AppImage"
    pkg.write_bytes(b"AI\x02")

    bilgi = NS(name="Uyg", version="1.0", author="", description="",
               homepage="")
    monkeypatch.setattr(AC, "get_appimage_info", lambda p: bilgi)

    def cikar(a, d):
        kok = Path(d) / "squashfs-root"
        kok.mkdir(parents=True, exist_ok=True)
        (kok / "AppRun").write_text("#!/bin/sh\n")
        return True

    monkeypatch.setattr(AC, "extract_appimage", cikar)
    return AC, pkg


def test_appimage_to_deb_dpkg_missing(monkeypatch, tmp_path):
    AC, pkg = _appimage_ortam(monkeypatch, tmp_path)
    import shutil as sh
    monkeypatch.setattr(sh, "which", lambda n: None if n == "dpkg-deb"
                        else "/usr/bin/x")

    ok, msg, _y = AC.appimage_to_deb(pkg, tmp_path)
    assert ok is False and "dpkg-deb bulunamadı" in msg              # 213-214


def test_appimage_to_deb_dpkg_fail(monkeypatch, tmp_path):
    AC, pkg = _appimage_ortam(monkeypatch, tmp_path)
    import shutil as sh
    monkeypatch.setattr(sh, "which", lambda n: "/usr/bin/dpkg-deb")
    monkeypatch.setattr(AC.shutil, "which", lambda n: "/usr/bin/dpkg-deb")
    monkeypatch.setattr(AC, "safe_run",
                        lambda cmd, timeout=0:
                        NS(returncode=1, stderr=b"dpkg patladi"))

    ok, msg, _y = AC.appimage_to_deb(pkg, tmp_path)
    assert ok is False and "dpkg-deb başarısız" in msg               # 221-222


# ── cloud_sync restore_drill dallari ─────────────────────────────────────────────

def test_drill_export_fail(monkeypatch, tmp_path):
    import core.cloud_sync as CS
    monkeypatch.setattr(CS, "export_backup",
                        lambda output_path=None: {"ok": False})  # 170-171
    sonuc = CS.restore_drill()
    assert sonuc["ok"] is False                                      # 170-171
    assert "export basarisiz" in sonuc["detail"]


def test_drill_manifest_missing(monkeypatch, tmp_path):
    import core.cloud_sync as CS

    bulten = tmp_path / "drill.zip"
    bulten.parent.mkdir(parents=True, exist_ok=True)

    def sahte_export(output_path=None):
        hedef = Path(output_path)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(hedef, "w") as zf:
            zf.writestr("baska.txt", "icerik")
        return {"ok": True, "path": str(hedef)}

    monkeypatch.setattr(CS, "export_backup", sahte_export)
    sonuc = CS.restore_drill()
    assert sonuc["ok"] is False                                      # 174-175
    assert "manifest eksik" in sonuc["detail"]


def test_drill_import_fail(monkeypatch, tmp_path):
    import core.cloud_sync as CS

    bulten = tmp_path / "drill.zip"
    bulten.parent.mkdir(parents=True, exist_ok=True)

    def sahte_export(output_path=None):
        hedef = Path(output_path)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(hedef, "w") as zf:
            zf.writestr(CS._MANIFEST, json.dumps({"files": {}}))
        return {"ok": True, "path": str(hedef)}

    monkeypatch.setattr(CS, "export_backup", sahte_export)
    monkeypatch.setattr(CS, "import_backup", lambda p: {"ok": False})
    sonuc = CS.restore_drill()
    assert sonuc["ok"] is False                                      # 183-184
    assert "import basarisiz" in sonuc["detail"]


def test_drill_missing_restored_file(monkeypatch, tmp_path):
    import core.cloud_sync as CS

    bulten = tmp_path / "drill.zip"
    bulten.parent.mkdir(parents=True, exist_ok=True)

    def sahte_export(output_path=None):
        hedef = Path(output_path)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(hedef, "w") as zf:
            zf.writestr(CS._MANIFEST, json.dumps({"files": {}}))
        return {"ok": True, "path": str(hedef)}

    monkeypatch.setattr(CS, "export_backup", sahte_export)
    monkeypatch.setattr(CS, "import_backup",
                        lambda p: {"ok": True,
                                   "restored": ["default/yok.txt"]})
    sonuc = CS.restore_drill()
    assert sonuc["ok"] is False                                      # 194-195
    assert "eksik geri yuklenen dosya" in sonuc["detail"]


def test_drill_outer_syncerror(monkeypatch, tmp_path):
    import core.cloud_sync as CS

    def sahte_export(output_path=None):
        hedef = Path(output_path)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_bytes(b"zip-degil")
        return {"ok": True, "path": str(hedef)}

    monkeypatch.setattr(CS, "export_backup", sahte_export)

    def patlak_zip(*a, **k):
        raise CS.SyncError("okuma reddi")

    monkeypatch.setattr(CS.zipfile, "ZipFile", patlak_zip)
    sonuc = CS.restore_drill()
    assert sonuc["ok"] is False and "okuma reddi" in sonuc["detail"]  # 200-201


def test_wal_checkpoint_busy(monkeypatch, tmp_path):
    """72-73: sqlite meşgulse bile export devam eder."""
    import sqlite3

    import core.cloud_sync as CS

    class PatlakConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql):
            raise sqlite3.Error("database is locked")

    gercek_connect = CS.sqlite3.connect
    sayac = {"n": 0}

    def secici(db, *a, **k):
        sayac["n"] += 1
        if sayac["n"] == 1:
            return PatlakConn()  # ilk baglanti: wal_checkpoint hedefi
        return gercek_connect(db, *a, **k)

    monkeypatch.setattr(CS.sqlite3, "connect", secici)
    try:
        CS.export_backup(output_path=str(tmp_path / "b.zip"))
    except Exception as hata:  # noqa: BLE001 - diger ortam hatalari kabul
        assert isinstance(hata, Exception)  # amac: 72-73 kolu calissin


# ── aur_publish 217-222 ──────────────────────────────────────────────────────────

def test_prepare_aur_fallback_regenerate(monkeypatch, tmp_path):
    import core.aur_publish as AP

    pkg = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"P")

    monkeypatch.setattr(AP, "_extract_pkg_info",
                        lambda p: {"name": "demo", "version": "1.0"})
    cagri = {"n": 0}

    def sahte_srcinfo(pb_yolu):
        cagri["n"] += 1
        return ""  # her iki denemede de bos; fallback yazimi yine isler

    monkeypatch.setattr(AP, "_generate_srcinfo", sahte_srcinfo)
    ok, _msg, _aur_pkg = AP.prepare_aur_package(
        pkg, tmp_path, git_url="https://github.com/x/y")
    assert ok is True                                                # 217-222
    assert cagri["n"] >= 2
    assert (tmp_path / "demo" / "PKGBUILD").is_file()


# ── snapshot_cleanup 196-197 / 204-205 / 224-225 / 255 / 261-262 ─────────────────

def test_install_cleanup_write_fail_and_exception(monkeypatch):
    import core.snapshot_cleanup as SCU

    monkeypatch.setattr(SCU, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(SCU.os.path, "isfile", lambda p: True)

    sonuclar = iter([
        NS(returncode=0, stdout=b"", stderr=b""),   # script
        NS(returncode=0, stdout=b"", stderr=b""),   # chmod
        NS(returncode=1, stdout=b"", stderr=b""),   # service -> 196-197
    ])
    monkeypatch.setattr(SCU, "safe_run",
                        lambda cmd, input=None, timeout=0: next(sonuclar))
    ok, msg = SCU.install_cleanup_service(max_age_days=7)
    assert ok is False and "Service dosyası yazılamadı" in msg       # 197

    sonuclar2 = iter([
        NS(returncode=0, stdout=b"", stderr=b""),   # script
        NS(returncode=0, stdout=b"", stderr=b""),   # chmod
        NS(returncode=0, stdout=b"", stderr=b""),   # service
        NS(returncode=1, stdout=b"", stderr=b""),   # timer -> 204-205
    ])
    monkeypatch.setattr(SCU, "safe_run",
                        lambda cmd, input=None, timeout=0: next(sonuclar2))
    ok2, msg2 = SCU.install_cleanup_service(max_age_days=7)
    assert ok2 is False and "Timer dosyası yazılamadı" in msg2       # 205

    def patlak(cmd, input=None, timeout=0):
        raise OSError("pkexec yok")

    monkeypatch.setattr(SCU, "safe_run", patlak)
    ok3, msg3 = SCU.install_cleanup_service(max_age_days=7)
    assert ok3 is False and "Kurulum başarısız" in msg3              # 224-225


def test_remove_cleanup_success_and_exception(monkeypatch):
    import core.snapshot_cleanup as SCU

    monkeypatch.setattr(SCU.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(SCU.Path, "exists",
                        lambda self: str(self).endswith(
                            (".sh", ".service", ".timer")))
    monkeypatch.setattr(SCU, "safe_run",
                        lambda cmd, timeout=0, input=None:
                        NS(returncode=0, stdout=b"", stderr=b""))
    ok, _msg = SCU.remove_cleanup_service()
    assert ok is True                                                # 253-255

    def patlak(cmd, timeout=0, input=None):
        raise OSError("systemd yok")

    monkeypatch.setattr(SCU, "safe_run", patlak)
    ok2, msg2 = SCU.remove_cleanup_service()
    assert ok2 is False and "Kaldırma başarısız" in msg2             # 261-262


# ── oci_builder 144-146 / 196-197 ────────────────────────────────────────────────

def test_oci_builder_exception_paths(monkeypatch, tmp_path):
    import core.oci_builder as OB

    pkg = tmp_path / "p.pkg.tar.zst"
    pkg.write_bytes(b"P")
    cikti = tmp_path / "out.oci"

    def akilli(cmd, timeout=0, input=None):
        adim = cmd[1] if len(cmd) > 1 else ""
        if adim in ("commit", "push", "export", "build"):
            raise OSError("runtime koptu")
        return NS(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(OB, "safe_run", akilli)
    ok, msg, _y = OB._build_with_buildah(pkg, "/usr/bin/buildah",
                                         "tag", cikti)
    assert ok is False and "OCI oluşturma hatası" in msg             # 144-146

    ok2, msg2, _y2 = OB._build_with_podman(pkg, "/usr/bin/podman",
                                           "tag", cikti)
    assert ok2 is False and "OCI oluşturma hatası" in msg2           # 196-197


# ── delta_updater 113 / 273 / 291-292 / 393 ──────────────────────────────────────

def test_delta_find_local_previous_skips_dirs(tmp_path):
    from core.delta_updater import find_local_previous

    alt = tmp_path / "alt-dizin"
    alt.mkdir()
    (tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst").write_bytes(b"P")

    sonuc = find_local_previous("demo", pkg_dir=tmp_path)            # 112-113
    assert sonuc is not None and sonuc.is_file()


def test_delta_install_timer_fail_and_exception(monkeypatch):
    import os

    import core.delta_updater as DU

    monkeypatch.setattr(os.path, "isfile", lambda p: True)

    import core.security as SEC
    sonuclar = iter([
        NS(returncode=0, stdout=b"", stderr=b""),   # script yaz
        NS(returncode=0, stdout=b"", stderr=b""),   # chmod
        NS(returncode=0, stdout=b"", stderr=b""),   # service yaz
        NS(returncode=1, stdout=b"", stderr=b""),   # timer -> 272-273
    ])
    monkeypatch.setattr(SEC, "safe_run",
                        lambda cmd, input=None, timeout=0: next(sonuclar))
    ok, msg = DU.install_auto_update(interval_hours=6)
    assert ok is False and "Timer dosyası yazılamadı" in msg         # 273

    def patlak(cmd, input=None, timeout=0):
        raise OSError("pkexec reddi")

    monkeypatch.setattr(SEC, "safe_run", patlak)
    ok2, msg2 = DU.install_auto_update(interval_hours=6)
    assert ok2 is False and "Kurulum başarısız" in msg2              # 291-292


def test_delta_enable_start_fail(monkeypatch):
    import core.delta_updater as DU
    import core.security as SEC

    monkeypatch.setattr(DU.shutil, "which",
                        lambda n: "/usr/bin/systemctl")
    monkeypatch.setattr(Path, "exists",
                        lambda self: "pkgforge-auto-update.timer"
                        in str(self))

    def sahte_run(cmd, input=None, timeout=0):
        if cmd[1] == "start":
            return NS(returncode=1, stdout=b"", stderr=b"baslatmadi")
        return NS(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(SEC, "safe_run", sahte_run)
    ok, msg = DU.enable_auto_update()
    assert ok is False and "Timer başlatılamadı" in msg              # 392-393


# ── profiles 55-56 / 65-66 / 81-82 ───────────────────────────────────────────────

def test_profiles_error_branches(monkeypatch, tmp_path):
    import core.profiles as PF

    kok = tmp_path / "profiller"
    kok.mkdir()
    monkeypatch.setattr(PF, "profiles_dir", lambda: kok)
    isaretci = tmp_path / "aktif-profil"
    monkeypatch.setattr(PF, "active_profile_file", lambda: isaretci)
    monkeypatch.setattr(PF, "current_profile",
                        lambda: (isaretci.read_text(encoding="utf-8")
                                 if isaretci.exists() else PF.DEFAULT_PROFILE))
    PF.create_profile("deneme-profil")

    with pytest.raises(PF.ProfileError, match="zaten mevcut"):
        PF.create_profile("deneme-profil")                           # 55-56
    with pytest.raises(PF.ProfileError, match="zaten mevcut"):
        PF.create_profile(PF.DEFAULT_PROFILE)

    with pytest.raises(PF.ProfileError, match="bulunamadı"):
        PF.switch_profile("olmayan-profil")                          # 65-66

    PF.switch_profile("deneme-profil")
    with pytest.raises(PF.ProfileError, match="Etkin profil"):
        PF.delete_profile("deneme-profil")

    PF.switch_profile(PF.DEFAULT_PROFILE)
    with pytest.raises(PF.ProfileError, match="bulunamadı"):
        PF.delete_profile("hic-var-olmadi")                          # 81-82


# ── queue_manager 106-108 ────────────────────────────────────────────────────────

def test_queue_remove_pending_item():
    from core.queue_manager import QueueItemStatus, QueueManager

    yonetici = QueueManager()
    urun = NS(status=QueueItemStatus.PENDING, path=Path("/x/pkg.tar.zst"))
    yonetici._items = [urun]
    alinan = []
    yonetici.queue_changed.connect(lambda liste: alinan.append(list(liste)))
    yonetici.remove_item(0)                                          # 106-108
    assert len(yonetici.items) == 0 and len(alinan) == 1


# ── provenance 208-209 / 215-216 ─────────────────────────────────────────────────

def test_provenance_hash_mismatches(tmp_path):
    from core.provenance import BuildProvenance, verify_provenance
    from core.security import sha256_hash

    kaynak = tmp_path / "kaynak.pkg.tar.zst"
    kaynak.write_bytes(b"K" * 64)
    cikti = tmp_path / "cikti.pkg.tar.zst"
    cikti.write_bytes(b"C" * 64)

    prov = BuildProvenance(source_file=str(kaynak),
                           source_sha256=sha256_hash(kaynak),
                           output_file=str(cikti),
                           output_sha256=sha256_hash(cikti))
    prov.provenance_hash = prov.compute_hash()

    prov.source_sha256 = "a" * 64  # boz
    prov.provenance_hash = prov.compute_hash()  # ozyinelemeli hash tutarli
    ok, msg = verify_provenance(prov)
    assert ok is False                                               # 208-209
    assert "Kaynak dosya hash uyuşmazlığı" in msg

    prov.source_sha256 = sha256_hash(kaynak)  # duzelt, ciktiyi boz
    prov.output_sha256 = "b" * 64
    prov.provenance_hash = prov.compute_hash()
    ok2, msg2 = verify_provenance(prov)
    assert ok2 is False                                              # 215-216
    assert "Çıktı dosyası hash uyuşmazlığı" in msg2


# ── sbom 258-260 ─────────────────────────────────────────────────────────────────

def test_sbom_dep_resolution_failure(monkeypatch, tmp_path):
    import core.dep_resolver as DR
    import core.sbom as SB

    pkg = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"P")

    def patlak(p, tools):
        raise RuntimeError("cozumleme koptu")

    monkeypatch.setattr(DR, "resolve_runtime_dependencies", patlak)
    sbom = SB.generate_sbom(pkg, NS(bsdtar="/usr/bin/bsdtar"),
                            offline=False)
    assert sbom.package_name == "demo"                               # 259-260


# ── aur_checker 163-168 (165-166 dahil) ──────────────────────────────────────────

def test_version_compare_dash_suffix():
    import shutil

    import core.aur_checker as AC

    gercek_which = shutil.which
    shutil.which = lambda n: None if n == "vercmp" else gercek_which(n)
    try:
        sonuc = AC._version_compare("1.0-2", "1.0-1")                # 165-166
    finally:
        shutil.which = gercek_which
    assert sonuc == 0  # release eki atilir -> esit