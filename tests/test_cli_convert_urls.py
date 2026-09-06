"""Coverage itmesi - cli convert URL/delta/verify-build/sign dallari."""
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
    base = {"target": str(target), "output_dir": str(tmp_path), "install": False,
            "dry_run": False, "yes": False, "to_oci": False, "oci_tag": None,
            "verify_build": False, "resolve_deps": False, "sign": False,
            "sign_key": None, "delta": False}
    base.update(kw)
    return NS(**base)


def _happy(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "discover_tools", _tools)
    pkg = tmp_path / "cikti.pkg.tar.zst"
    pkg.write_bytes(b"P")
    monkeypatch.setattr(BR, "convert_deb_sync",
                        lambda fp, od, tools=None, progress_callback=None:
                        NS(success=True, message="ok", output_pkg=pkg))
    monkeypatch.setattr(BR, "convert_rpm_sync",
                        lambda fp, od, tools=None, progress_callback=None:
                        NS(success=True, message="ok", output_pkg=pkg))
    db = FakeDB()
    monkeypatch.setattr(cli, "HistoryDB", lambda: db)
    import core.provenance as PRV
    monkeypatch.setattr(PRV, "create_provenance", lambda **kw: NS())
    monkeypatch.setattr(PRV, "save_provenance", lambda pr, p: Path(p))
    return db, pkg


def test_convert_url_download_fail(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "discover_tools", _tools)

    def boom(url, require_https=True, response_info=None, **k):
        raise RuntimeError("ag yok")
    monkeypatch.setattr(cli, "download_package", boom)
    rc = cli._cmd_convert(_args(tmp_path, "https://ornek.test/x.deb"))
    assert rc == 1 and "ag yok" in capsys.readouterr().out


def test_convert_url_download_ok(capsys, monkeypatch, tmp_path):
    db, _pkg = _happy(monkeypatch, tmp_path)
    f = tmp_path / "indirilen.deb"
    f.write_bytes(b"D")
    monkeypatch.setattr(cli, "download_package",
                        lambda url, require_https=True, response_info=None, **k: f)
    rc = cli._cmd_convert(_args(tmp_path, "https://ornek.test/x.deb"))
    assert rc == 0
    assert db.added[0]["source_url"].startswith("https://")


def test_convert_url_delta(capsys, monkeypatch, tmp_path):
    import core.delta_updater as DU
    _happy(monkeypatch, tmp_path)
    f = tmp_path / "delta.deb"
    f.write_bytes(b"D")
    monkeypatch.setattr(DU, "find_local_previous", lambda n, **k: None)

    def fake_dl(url, dest, old_pkg=None, require_https=True, **k):
        Path(dest).write_bytes(b"D")
        return Path(dest), False
    monkeypatch.setattr(DU, "download_with_delta", fake_dl)
    monkeypatch.setattr("i18n.load_setting", lambda k, d=False: False)
    rc = cli._cmd_convert(_args(tmp_path, "https://ornek.test/y.deb", delta=True))
    assert rc == 0


def test_convert_verify_build_flag(capsys, monkeypatch, tmp_path):
    import core.reproducible_build as RB
    _happy(monkeypatch, tmp_path)
    f = tmp_path / "v.deb"
    f.write_bytes(b"D")
    monkeypatch.setattr(RB, "verify_reproducible",
                        lambda p, t: NS(verified=True, detail="ayni"))
    rc = cli._cmd_convert(_args(tmp_path, f, verify_build=True))
    out = capsys.readouterr().out
    assert rc == 0 and "reproducible" in out


def test_convert_resolve_deps_and_grade(capsys, monkeypatch, tmp_path):
    import core.package_analyzer as PA
    _happy(monkeypatch, tmp_path)
    f = tmp_path / "r.rpm"
    f.write_bytes(b"R")
    monkeypatch.setattr(PA, "analyze_package",
                        lambda p, t: NS(file_list=[], depends=[], name="n",
                                        version="1"))
    import core.compatibility_checker as CC
    monkeypatch.setattr(CC, "run_compatibility_checks",
                        lambda *a, **k: NS(grade="A", overall=NS(value="pass"),
                                           checks=[]))
    import core.dep_resolver as DR
    monkeypatch.setattr(DR, "resolve_dependencies",
                        lambda deps: NS(summary=lambda: "cozuldu",
                                        all_resolved=True, deps=[]))
    rc = cli._cmd_convert(_args(tmp_path, f, resolve_deps=True))
    out = capsys.readouterr().out
    assert rc == 0 and "cozuldu" in out and "A" in out, out[-400:]


def test_convert_sign_flag(capsys, monkeypatch, tmp_path):
    import core.package_signing as PS
    _happy(monkeypatch, tmp_path)
    f = tmp_path / "s.deb"
    f.write_bytes(b"D")
    signed = {}

    def fake_sign(p, key=None):
        signed["pkg"] = p
        return True, "imzalandi"
    monkeypatch.setattr(PS, "sign_package", fake_sign)
    rc = cli._cmd_convert(_args(tmp_path, f, sign=True))
    assert rc == 0 and signed["pkg"].name == "cikti.pkg.tar.zst"
    assert "imzalandi" in capsys.readouterr().out


def test_convert_dry_run_note(capsys, monkeypatch, tmp_path):
    db, _pkg = _happy(monkeypatch, tmp_path)
    f = tmp_path / "d.deb"
    f.write_bytes(b"D")
    rc = cli._cmd_convert(_args(tmp_path, f, install=True, dry_run=True))
    assert rc == 0 and db.added[0]["status"] == "converted"


def test_convert_oci_failure(capsys, monkeypatch, tmp_path):
    import core.oci_builder as OB
    _happy(monkeypatch, tmp_path)
    f = tmp_path / "o.deb"
    f.write_bytes(b"D")
    monkeypatch.setattr(OB, "build_oci_image",
                        lambda p, t, tag=None: (False, "runtime yok", None))
    rc = cli._cmd_convert(_args(tmp_path, f, to_oci=True))
    assert rc == 1 and "runtime yok" in capsys.readouterr().out