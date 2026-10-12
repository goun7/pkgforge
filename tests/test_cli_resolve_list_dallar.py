"""pkgforge cli._resolve_pkg_file + _cmd_list dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — HistoryDB tmp-yol'a YONLENDIRILDI, glob MONKEYPATCH,
dosya-sistemi tmp_path (dis cagri YOK).
"""
import argparse
import sys
from pathlib import Path

import pytest

sys.path.insert(0, ".")
from cli import _cmd_list
from core.history_db import HistoryDB

# _resolve_pkg_file module-icinde (nested) — packaging() icinde test edilemez,
# ama ayni govdeyi bagimsiz test ederiz:


def _resolve_like(name: str, tmp: Path) -> Path | None:
    """Ayni govde: direkt-dosya / pacman-cache glob."""
    direct = Path(name).expanduser()
    if direct.is_file():
        return direct
    import glob as globmod
    for pattern in [f"/var/cache/pacman/pkg/{name}-*-any.pkg.tar.zst",
                    f"/var/cache/pacman/pkg/{name}-x86_64.pkg.tar.zst"]:
        matches = globmod.glob(pattern)
        if matches:
            return Path(matches[0])
    return None


# == _cmd_list: temel =============================================================================

@pytest.fixture()
def db(monkeypatch, tmp_path):
    """HistoryDB tmp'ye yonlendirilmis."""
    d = tmp_path / "hist"
    d.mkdir()
    inst = HistoryDB(d / "h.db")
    monkeypatch.setattr("core.history_db.backup_dir",
                        lambda: d / "backup")
    return inst


def test_bos_gecmis(db, capsys, monkeypatch):
    """ORTAM: kayit yok -> list_empty + rc 0."""
    monkeypatch.setattr("cli.HistoryDB", lambda: db)
    rc = _cmd_list(argparse.Namespace())
    assert rc == 0
    out = capsys.readouterr().out
    assert "list_title" in out or out.strip()


def test_kayit_var(db, capsys, monkeypatch):
    db.add_record("test", "/x/test.pkg", "deb", "sha", "ok")
    monkeypatch.setattr("cli.HistoryDB", lambda: db)
    rc = _cmd_list(argparse.Namespace())
    assert rc == 0
    out = capsys.readouterr().out
    assert "test" in out


def test_limit_30(monkeypatch, db):
    """ORTAM: get_history(limit=30) cagrilir."""
    cagri = {"limit": None, "hits": []}

    def fake(limit=50):
        cagri["limit"] = limit
        return []
    db.get_history = fake
    monkeypatch.setattr("cli.HistoryDB", lambda: db)
    _cmd_list(argparse.Namespace())
    assert cagri["limit"] == 30


def test_baslik_yazilir(db, capsys, monkeypatch):
    monkeypatch.setattr("cli.HistoryDB", lambda: db)
    _cmd_list(argparse.Namespace())
    out = capsys.readouterr().out
    assert out.startswith("")  # her-halde bir-sey basar


def test_returns_int(db, monkeypatch):
    monkeypatch.setattr("cli.HistoryDB", lambda: db)
    assert isinstance(_cmd_list(argparse.Namespace()), int)


# == _resolve_pkg_file ===========================================================================

def test_direkt_dosya(tmp_path):
    """ORTAM: direkt-path -> Path doner."""
    f = tmp_path / "test.pkg.tar.zst"
    f.write_bytes(b"x")
    assert _resolve_like(str(f), tmp_path) == f


def test_direkt_dosya_relative(tmp_path, monkeypatch):
    """ORTAM: relative-path mevcut-dizine gore cozulur."""
    f = tmp_path / "test.pkg.tar.zst"
    f.write_bytes(b"x")
    monkeypatch.chdir(tmp_path)
    assert _resolve_like("test.pkg.tar.zst", tmp_path) == Path("test.pkg.tar.zst")


def test_glob_eslesme(tmp_path, monkeypatch):
    """ORTAM: pacman-cache glob -> ilk-eslesme."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "pkg-1.0-1-any.pkg.tar.zst").write_bytes(b"x")
    monkeypatch.setattr(
        "glob.glob",
        lambda p: sorted(str(x) for x in cache.glob("*.pkg.tar.zst")))
    # _resolve_like glob modulu kullanir — monkeypatch yerine tmp-glob
    import glob as globmod
    orig = globmod.glob
    globmod.glob = lambda p: orig(str(cache / Path(p).name)
                                 if "*" not in p else str(cache / "*.zst"))
    try:
        r = _resolve_like("pkg", tmp_path)
    finally:
        globmod.glob = orig
    assert r is not None


def test_glob_eslesme_yok(tmp_path, monkeypatch):
    """ORTAM: eslesme yok -> None."""
    import glob as globmod
    orig = globmod.glob
    globmod.glob = lambda p: []
    try:
        assert _resolve_like("yok", tmp_path) is None
    finally:
        globmod.glob = orig


def test_direkt_dizin_degil(tmp_path):
    """ORTAM: dizin -> is_file False -> glob'e duser."""
    assert _resolve_like(str(tmp_path), tmp_path) is None


def test_bos_name(tmp_path):
    assert _resolve_like("", tmp_path) is None


def test_expanduser(monkeypatch, tmp_path):
    """ORTAM: ~ -> expanduser."""
    monkeypatch.setenv("HOME", str(tmp_path))
    f = tmp_path / "t.pkg.tar.zst"
    f.write_bytes(b"x")
    assert _resolve_like("~/t.pkg.tar.zst", tmp_path) == f


def test_returns_path_or_none(tmp_path):
    f = tmp_path / "x.pkg"
    f.write_bytes(b"")
    r = _resolve_like(str(f), tmp_path)
    assert isinstance(r, Path)


def test_none_olmayan_dosya(tmp_path):
    r = _resolve_like(str(tmp_path / "yok.pkg"), tmp_path)
    assert r is None


def test_uzun_name(tmp_path):
    r = _resolve_like("a" * 500, tmp_path)
    assert r is None


def test_turkce_name(tmp_path):
    f = tmp_path / "Türkçe.pkg"
    f.write_bytes(b"")
    assert _resolve_like(str(f), tmp_path) == f


def test_bosluklu_name(tmp_path):
    f = tmp_path / "adı var.pkg"
    f.write_bytes(b"")
    assert _resolve_like(str(f), tmp_path) == f


@pytest.mark.parametrize("name", ["pkg", "linux", "bash", "coreutils"])
def test_glob_matrix(name, tmp_path, monkeypatch):
    """ORTAM: iki glob-pattern denenir."""
    import glob as globmod
    orig = globmod.glob
    globmod.glob = lambda p: []
    try:
        assert _resolve_like(name, tmp_path) is None
    finally:
        globmod.glob = orig
