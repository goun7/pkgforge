"""Tur-24 — scheduler/policy/cross_check/rollback/downloader son dallari."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

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