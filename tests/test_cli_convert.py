"""Coverage itmesi — cli _cmd_convert ana akisi."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import cli
import core.cli_bridge as BR


class FakeDB:
    def __init__(self):
        self.added = []

    def backup_package(self, p):
        return None

    def add_record(self, **kw):
        self.added.append(kw)


def _tools():
    return NS(missing_required=[], missing_optional=[], pkexec="pkexec",
              pacman="pacman")


def _args(tmp_path, target, **kw):
    base = dict(target=str(target), output_dir=str(tmp_path), install=False,
                dry_run=False, yes=False, to_oci=False, oci_tag=None,
                verify_build=False, resolve_deps=False, sign=False,
                sign_key=None, delta=False)
    base.update(kw)
    return NS(**base)


def _patch_happy(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "discover_tools", _tools)
    pkg = tmp_path / "cikti.pkg.tar.zst"
    pkg.write_bytes(b"P")

    def fake_sync(fp, od, tools=None, progress_callback=None):
        return NS(success=True, message="ok", output_pkg=pkg)
    monkeypatch.setattr(BR, "convert_deb_sync", fake_sync)
    monkeypatch.setattr(BR, "convert_rpm_sync", fake_sync)
    db = FakeDB()
    monkeypatch.setattr(cli, "HistoryDB", lambda: db)
    import core.provenance as PRV
    monkeypatch.setattr(PRV, "create_provenance", lambda **kw: NS())
    monkeypatch.setattr(PRV, "save_provenance", lambda pr, p: Path(p))
    return db, pkg


def test_convert_missing_tools(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "discover_tools",
                        lambda: NS(missing_required=["bsdtar"], missing_optional=[]))
    rc = cli._cmd_convert(_args(tmp_path, tmp_path / "yok.deb"))
    assert rc == 1
    out = capsys.readouterr().out.lower()
    assert "araç" in out or "tool" in out or "bulunamad" in out


def test_convert_local_missing(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "discover_tools", _tools)
    rc = cli._cmd_convert(_args(tmp_path, tmp_path / "yok.deb"))
    assert rc == 1 and "bulunamad" in capsys.readouterr().out


def test_convert_deb_happy(capsys, monkeypatch, tmp_path):
    db, pkg = _patch_happy(monkeypatch, tmp_path)
    f = tmp_path / "girdi.deb"
    f.write_bytes(b"D")
    rc = cli._cmd_convert(_args(tmp_path, f))
    assert rc == 0 and len(db.added) == 1
    assert db.added[0]["status"] == "converted"
    assert db.added[0]["package_type"] == "deb"
    out = capsys.readouterr().out
    assert "Provenance" in out


def test_convert_rpm_happy(capsys, monkeypatch, tmp_path):
    db, pkg = _patch_happy(monkeypatch, tmp_path)
    f = tmp_path / "girdi.rpm"
    f.write_bytes(b"R")
    rc = cli._cmd_convert(_args(tmp_path, f))
    assert rc == 0 and db.added[0]["package_type"] == "rpm"


def test_convert_conversion_fail(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "discover_tools", _tools)
    f = tmp_path / "g.deb"
    f.write_bytes(b"D")
    monkeypatch.setattr(BR, "convert_deb_sync",
                        lambda fp, od, tools=None, progress_callback=None:
                        NS(success=False, message="kirik", output_pkg=None))
    rc = cli._cmd_convert(_args(tmp_path, f))
    assert rc == 1 and "kirik" in capsys.readouterr().out


def test_convert_install_yes_success(capsys, monkeypatch, tmp_path):
    db, pkg = _patch_happy(monkeypatch, tmp_path)
    f = tmp_path / "g.deb"
    f.write_bytes(b"D")
    monkeypatch.setattr(cli, "safe_run", lambda cmd, timeout=None, **kw:
                        NS(returncode=0, stdout="", stderr=""))
    rc = cli._cmd_convert(_args(tmp_path, f, install=True, yes=True))
    assert rc == 0 and db.added[0]["status"] == "installed"


def test_convert_install_fail(capsys, monkeypatch, tmp_path):
    db, pkg = _patch_happy(monkeypatch, tmp_path)
    f = tmp_path / "g.deb"
    f.write_bytes(b"D")
    monkeypatch.setattr(cli, "safe_run", lambda cmd, timeout=None, **kw:
                        NS(returncode=1, stdout="", stderr="pacman kizgin"))
    rc = cli._cmd_convert(_args(tmp_path, f, install=True, yes=True))
    assert rc == 1 and db.added[0]["status"] == "install_failed"


def test_convert_install_declined_noninteractive(capsys, monkeypatch, tmp_path):
    db, pkg = _patch_happy(monkeypatch, tmp_path)
    f = tmp_path / "g.deb"
    f.write_bytes(b"D")
    rc = cli._cmd_convert(_args(tmp_path, f, install=True, yes=False))
    assert rc == 0 and db.added[0]["status"] == "converted"


def test_convert_to_oci(capsys, monkeypatch, tmp_path):
    import core.oci_builder as OB
    db, pkg = _patch_happy(monkeypatch, tmp_path)
    f = tmp_path / "g.deb"
    f.write_bytes(b"D")
    oci = tmp_path / "c.oci.tar"
    monkeypatch.setattr(OB, "build_oci_image",
                        lambda p, t, tag=None: (True, "oci hazir", oci))
    rc = cli._cmd_convert(_args(tmp_path, f, to_oci=True))
    assert rc == 0 and db.added[0]["status"] == "oci_built"
