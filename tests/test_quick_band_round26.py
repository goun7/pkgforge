"""Tur-26 — hizli bant: security/quality/analyzer/delta son dallari."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.delta_updater as DU
import core.package_analyzer as PA
import core.quality_score as QS
import core.security as SEC

TOOLS = NS(rpm2cpio="/usr/bin/rpm2cpio",
           file_cmd="/usr/bin/file")


# --- security --------------------------------------------------------------------

def test_mime_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        SEC.validate_mime_type(tmp_path / "yok.deb", TOOLS)


def test_mime_invalid_type_rejected(monkeypatch, tmp_path):
    f = tmp_path / "x.deb"
    f.write_bytes(b"D")
    monkeypatch.setattr("subprocess.run",
                        lambda *a, **k: NS(returncode=0, stdout="text/plain"))
    with pytest.raises(ValueError, match="Geçersiz dosya türü"):
        SEC.validate_mime_type(f, TOOLS)


def test_bomb_rpm_garbage_sizes_swallowed(monkeypatch, tmp_path):
    f = tmp_path / "buyuk.rpm"
    f.write_bytes(b"x" * 200_000)          # >0.1MB
    monkeypatch.setattr(SEC, "safe_run",
                        lambda *a, **k: NS(returncode=0,
                                           stdout="abc\ndef\n"))
    assert SEC.check_compression_bomb(f, TOOLS) is None


def test_safe_resolve_fallback(monkeypatch, tmp_path):
    def patla(self, strict=False):
        raise OSError("cozulemedi")
    monkeypatch.setattr(Path, "resolve", patla)
    hedef = SEC._safe_resolve(tmp_path / "alt" / ".." / "d.osya")
    assert hedef.name == "d.osya" and "alt" not in hedef.parts


def test_dangerous_files_lstat_error_skipped(monkeypatch, tmp_path):
    (tmp_path / "girdi").write_text("i")
    gercek_lstat = Path.lstat

    def sahte(self, *a, **k):
        if self.name == "girdi":
            raise OSError("lstat basarisiz")
        return gercek_lstat(self, *a, **k)

    monkeypatch.setattr(Path, "lstat", sahte)
    hatalar, uyarilar = SEC.check_dangerous_files(tmp_path)[:2] \
        if isinstance(SEC.check_dangerous_files(tmp_path), tuple) \
        else (SEC.check_dangerous_files(tmp_path).errors,
              SEC.check_dangerous_files(tmp_path).warnings)
    assert hatalar == [] and uyarilar == []


# --- quality_score ---------------------------------------------------------------

def _bos_paket(tmp_path):
    p = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    p.write_bytes(b"P")
    return p


def test_clamav_exception_fallback(monkeypatch, tmp_path):
    pkg = _bos_paket(tmp_path)

    def patla():
        raise RuntimeError("clamav kirik")
    monkeypatch.setattr("core.malware_scanner.is_clamav_available", patla)
    rapor = QS.score_package(pkg, TOOLS)
    malware = next(c for c in rapor.checks
                   if c.name == "Malware Taraması")
    assert malware.passed is True and malware.score == 5


def test_midsize_and_filecount_scores(monkeypatch, tmp_path):
    monkeypatch.setattr("core.abi_scanner.check_abi_compatibility",
                        lambda p: NS(passed=True, binary_count=1,
                                     error_count=0))
    pkg = tmp_path / "orta-1.0-1-x86_64.pkg.tar.zst"
    with open(pkg, "wb") as fh:
        fh.seek(700 * 1024 * 1024)          # seyrek dosya: 700MB gorunur
        fh.write(b"x")
    satirlar = "\n".join(f"dosya{i}" for i in range(6000))
    monkeypatch.setattr(QS, "safe_run",
                        lambda *a, **k: NS(returncode=0, stdout=satirlar))
    rapor = QS.score_package(pkg, TOOLS)
    boyut = next(c for c in rapor.checks if c.name == "Paket Boyutu")
    adet = next(c for c in rapor.checks if c.name == "Dosya Sayısı")
    assert boyut.score == 4 and "700" in boyut.detail
    assert adet.score == 4 and adet.detail == "6000 dosya"


def test_grade_f_when_everything_bad(monkeypatch, tmp_path):
    pkg = _bos_paket(tmp_path)
    monkeypatch.setattr("core.abi_scanner.check_abi_compatibility",
                        lambda p: NS(passed=False, error_count=5,
                                     binary_count=3))
    monkeypatch.setattr("core.malware_scanner.is_clamav_available",
                        lambda: True)
    monkeypatch.setattr("core.malware_scanner.scan_file",
                        lambda p, t: NS(clean=False, detail="zararli"))
    monkeypatch.setattr(QS, "safe_run",
                        lambda *a, **k: NS(returncode=1, stdout=""))
    rapor = QS.score_package(pkg, TOOLS)
    assert rapor.grade == "F"


# --- package_analyzer ------------------------------------------------------------

def test_rpm_filename_release_suffix():
    meta = PA.PackageMetadata()
    PA._parse_rpm_filename(Path("app-1.0-2.fc40.x86_64.rpm"), meta)
    assert meta.name == "app"
    assert meta.version == "1.0-2.fc40"
    assert meta.arch == "x86_64"


# --- delta_updater ---------------------------------------------------------------

def test_find_local_previous_default_dir_missing(monkeypatch, tmp_path):
    sahte_conf = tmp_path / "conf"
    sahte_conf.mkdir()
    monkeypatch.setitem(__import__("sys").modules, "config",
                        NS(CONFIG_DIR=sahte_conf))
    assert DU.find_local_previous("demo", None) is None


def test_install_auto_update_service_write_fail(monkeypatch):
    monkeypatch.setattr("os.path.isfile", lambda p: True)

    def hedefli_run(cmd, timeout=0, input=None, **k):
        birlesik = " ".join(str(c) for c in cmd)
        if "service-deploy" in birlesik:
            return NS(returncode=1, stderr="redd")
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("core.security.safe_run", hedefli_run)
    ok, msg = DU.install_auto_update(interval_hours=6)
    # Faz 14: tek write-batch — ret kodu tek mesajdan yuzeye cikar.
    assert ok is False and "yazılamadı" in msg


def test_enable_auto_update_enable_failure(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/systemctl")
    gercek_exists = Path.exists
    sabit = ("/etc/systemd/system/pkgforge-auto-update.timer",
             "/etc/systemd/system/pkgforge-auto-update.service")

    def sahte_exists(self):
        if str(self) in sabit:
            return True
        return gercek_exists(self)

    monkeypatch.setattr(Path, "exists", sahte_exists)

    cagri = {"n": 0}
    def sahte_run(cmd, timeout=0, **k):
        cagri["n"] += 1
        if any("enable" in str(c) for c in cmd):
            return NS(returncode=1, stderr="etkinlesmedi")
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr("core.security.safe_run", sahte_run)
    ok, msg = DU.enable_auto_update()
    assert ok is False and "etkinleştirilemedi" in msg


def test_disable_auto_update_without_systemctl(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    ok, msg = DU.disable_auto_update()
    assert ok is False and "systemd kurulu değil" in msg