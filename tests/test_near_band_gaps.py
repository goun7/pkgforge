"""Tur-24 — scheduler/policy/cross_check/rollback/downloader son dallari."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.cross_check as CC
import core.downloader as DL
import core.policy_engine as PE
import core.rollback_verify as RV
import core.scheduler as SCH

# --- policy_engine._extract_overall ---------------------------------------------

def test_overall_dict_checks_not_list():
    assert PE._extract_overall({"checks": "bozuk"}) is None


def test_overall_invalid_severity_skipped():
    rapor = {"checks": [{"severity": "garbage"},
                        {"severity": "error"}]}
    sonuc = PE._extract_overall(rapor)
    assert sonuc is not None and sonuc.value == "error"


def test_overall_non_dict_non_report_returns_none():
    assert PE._extract_overall(["liste"]) is None


# --- cross_check._query_flatpak_version -----------------------------------------

def _flatpak_satirlar(satirlar):
    return NS(returncode=0, stdout="\n".join(satirlar) + "\n")


def test_flatpak_query_matches_row(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/flatpak")
    monkeypatch.setattr(CC, "safe_run",
                        lambda cmd, timeout=0: _flatpak_satirlar([
                            "Name\tID\tVersion\tBranch",
                            "GTK App\torg.gtk.App\tx\t3.24",
                            "Diger\torg.diger\tx\t1.0",
                        ]))
    assert CC._query_flatpak_version("gtk app") == "3.24"


def test_flatpak_query_no_match(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/flatpak")
    monkeypatch.setattr(CC, "safe_run",
                        lambda cmd, timeout=0: _flatpak_satirlar([
                            "Name\tID\tVersion\tBranch",
                            "Baska\torg.baska\tx\t9.9",
                        ]))
    assert CC._query_flatpak_version("yok-olan") == ""


def test_flatpak_query_short_rows_ignored(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/flatpak")
    monkeypatch.setattr(CC, "safe_run",
                        lambda cmd, timeout=0: _flatpak_satirlar([
                            "Header\tsadece\tikili",
                            "kisa\tsatir",
                        ]))
    assert CC._query_flatpak_version("x") == ""


def test_flatpak_query_exception(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/flatpak")

    def patla(cmd, timeout=0):
        raise OSError("flatpak calismiyor")
    monkeypatch.setattr(CC, "safe_run", patla)
    assert CC._query_flatpak_version("herhangibirsey") == ""


def test_flatpak_query_without_binary_or_name(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert CC._query_flatpak_version("x") == ""
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/flatpak")
    assert CC._query_flatpak_version("") == ""


# --- rollback_verify._hash_file_tree --------------------------------------------

KEY_DIRS = ("/etc", "/usr/bin", "/usr/lib")


def _hepsini_yok_say(monkeypatch):
    gercek_exists = Path.exists
    def sahte(self):
        if str(self) in KEY_DIRS:
            return False
        return gercek_exists(self)
    monkeypatch.setattr(Path, "exists", sahte)


def test_hash_tree_missing_dirs_still_hashes(monkeypatch):
    _hepsini_yok_say(monkeypatch)
    ozet = RV._hash_file_tree(Path("/"))
    assert isinstance(ozet, str) and len(ozet) == 64   # bos hash


def test_hash_tree_outer_permission_error(monkeypatch, tmp_path):
    gercek_exists = Path.exists
    def sahte_exists(self):
        if str(self) in KEY_DIRS:
            return True
        return gercek_exists(self)
    monkeypatch.setattr(Path, "exists", sahte_exists)

    def sahte_iterdir(self):
        if str(self) == "/usr/bin":
            raise PermissionError(13, "yasak")
        return iter(())
    monkeypatch.setattr(Path, "iterdir", sahte_iterdir)
    ozet = RV._hash_file_tree(Path("/"))
    assert len(ozet) == 64


def test_hash_tree_inner_stat_error(monkeypatch, tmp_path):
    gercek_exists = Path.exists
    def sahte_exists(self):
        if str(self) in KEY_DIRS:
            return True
        return gercek_exists(self)
    monkeypatch.setattr(Path, "exists", sahte_exists)

    dosya = tmp_path / "f"
    gercek_iterdir = Path.iterdir
    def sahte_iterdir(self):
        if str(self) == "/etc":
            return iter([dosya])
        return gercek_iterdir(self)
    monkeypatch.setattr(Path, "iterdir", sahte_iterdir)

    gercek_isfile = Path.is_file
    def sahte_isfile(self):
        if self == dosya:
            return True
        return gercek_isfile(self)
    monkeypatch.setattr(Path, "is_file", sahte_isfile)

    gercek_stat = Path.stat
    def sahte_stat(self, *a, **k):
        if self == dosya:
            raise PermissionError(13, "okunmaz")
        return gercek_stat(self, *a, **k)
    monkeypatch.setattr(Path, "stat", sahte_stat)

    ozet = RV._hash_file_tree(Path("/"))
    assert len(ozet) == 64


# --- scheduler bulut gorevleri --------------------------------------------------

def _sahte_bulut(monkeypatch):
    kayit = {}
    monkeypatch.setitem(sys.modules, "core.cloud_sync", NS(
        webdav_push=lambda: {"ok": True, "detail": "push"},
        export_backup=lambda: {"ok": True, "detail": "export"},
        restore_drill=lambda: {"ok": True, "detail": "drill"},
    ))
    return kayit


def test_scheduler_sync_push(monkeypatch):
    _sahte_bulut(monkeypatch)
    out = SCH._task_sync_push()
    assert out["ok"] is True and "push" in out["detail"]


def test_scheduler_backup_export(monkeypatch):
    _sahte_bulut(monkeypatch)
    out = SCH._task_backup_export()
    assert out["ok"] is True and "export" in out["detail"]


def test_scheduler_restore_drill(monkeypatch):
    _sahte_bulut(monkeypatch)
    out = SCH._task_restore_drill()
    assert out["ok"] is True and "drill" in out["detail"]


# --- downloader._open_url -------------------------------------------------------

def test_open_url_builds_guarded_opener(monkeypatch):
    acilan = []

    class SahteOpener:
        def __init__(self, handler):
            acilan.append(("handler", handler))
        def open(self, req, timeout=None):
            acilan.append(("open", req, timeout))
            return "yanit"

    monkeypatch.setattr(DL.urllib.request, "build_opener",
                        lambda handler: SahteOpener(handler))
    istek = NS(full_url="https://ornek/f.deb")
    yanit = DL._open_url(istek, timeout=7, require_https=True)
    assert yanit == "yanit"
    assert acilan[0][1]._require_https is True
    assert acilan[1] == ("open", istek, 7)

# --- tur-24 ekleri: son dort satir ----------------------------------------------

def test_verify_rollback_restore_mismatch(monkeypatch):
    snap = NS(snapshot_name="s1", success=True, detail="")
    monkeypatch.setattr(RV, "detect_backend", lambda: "btrfs")
    monkeypatch.setattr(RV, "take_snapshot", lambda name: snap)
    monkeypatch.setitem(sys.modules, "core.snapshot_manager",
                        NS(restore_snapshot=lambda name: (True, "ok")))
    degerler = iter(["aaaa1111aaaa1111", "bbbb2222bbbb2222"])
    monkeypatch.setattr(RV, "_hash_file_tree",
                        lambda root, max_files=100: next(degerler))
    sonuc = RV.verify_rollback_restore()
    assert sonuc.verified is False
    assert "farklı" in sonuc.detail


def _indirme_ortemi(monkeypatch, tmp_path, url, chunklar):
    yanit = NS(
        headers=NS(get=lambda k, d="": ""),
        read=(lambda n=0: chunklar.pop(0) if chunklar else b""),
        __enter__=lambda s: s,
        __exit__=lambda s, *a: False,
    )
    class Yanit:
        def __enter__(self_inner):
            return yanit
        def __exit__(self_inner, *a):
            return False
    monkeypatch.setattr(DL, "_open_url",
                        lambda req, timeout=0, require_https=True: Yanit())
    monkeypatch.setattr(DL, "create_temp_dir", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "core.retry", NS(
        RetryConfig=lambda **k: NS(**k),
        retry_with_backoff=lambda fn, config=None, operation_name=None: fn(),
    ))


def test_download_filename_fallback_and_tempdir(monkeypatch, tmp_path):
    _indirme_ortemi(monkeypatch, tmp_path, "https://host/pkg-deb-stub",
                    [b"veri", b""])
    hedef = DL.download_package("https://host/pkg-deb-stub", None)
    assert hedef.name == "downloaded_package.deb"
    assert hedef.parent == tmp_path


def test_download_size_limit_exceeded(monkeypatch, tmp_path):
    monkeypatch.setattr(DL, "MAX_PACKAGE_SIZE_MB", 0)
    buyuk = b"x" * 70000          # tek parca bile siniri asar
    _indirme_ortemi(monkeypatch, tmp_path, "https://host/a.deb",
                    [buyuk, b""])
    with pytest.raises(RuntimeError, match="maksimum"):
        DL.download_package("https://host/a.deb", tmp_path)