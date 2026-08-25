"""Coverage itmesi - cli kucuk komutlar: remove/rollback/quality/publish/delta."""
from __future__ import annotations

from types import SimpleNamespace as NS

import cli


def _tools():
    return NS(missing_required=[], missing_optional=[], pkexec="pk", pacman="pm")


def test_remove_success_and_fail(capsys, monkeypatch):
    monkeypatch.setattr(cli, "discover_tools", _tools)
    monkeypatch.setattr(cli, "safe_run", lambda cmd, timeout=None, **kw:
                        NS(returncode=0, stdout="", stderr=""))
    rc = cli._cmd_remove(NS(package="demo"))
    assert rc == 0 and "kaldırıldı" in capsys.readouterr().out.lower()

    monkeypatch.setattr(cli, "safe_run", lambda cmd, timeout=None, **kw:
                        NS(returncode=1, stdout="", stderr="hata"))
    rc2 = cli._cmd_remove(NS(package="demo"))
    assert rc2 == 1

    rc3 = cli._cmd_remove(NS(package="--kotu;ad"))
    assert rc3 == 1


def test_rollback_no_backup(capsys, monkeypatch, tmp_path):
    class FakeDB:
        def get_records_for_package(self, n):
            return []
    monkeypatch.setattr(cli, "HistoryDB", FakeDB)
    monkeypatch.setattr(cli, "discover_tools", _tools)
    rc = cli._cmd_rollback(NS(package="yok-paket"))
    assert rc == 1 and "yedek" in capsys.readouterr().out.lower()


def test_quality_paths(capsys, monkeypatch, tmp_path):
    import core.quality_score as QS
    rc = cli._cmd_quality(NS(package=str(tmp_path / "yok.zst")))
    assert rc == 1 and "bulunamadı" in capsys.readouterr().out

    f = tmp_path / "p.pkg.tar.zst"
    f.write_bytes(b"x")
    monkeypatch.setattr(cli, "discover_tools", _tools)
    monkeypatch.setattr(QS, "score_package",
                        lambda p, t: NS(summary=lambda: "skor 92", passed=True))
    rc2 = cli._cmd_quality(NS(package=str(f)))
    assert rc2 == 0 and "skor 92" in capsys.readouterr().out

    monkeypatch.setattr(QS, "score_package",
                        lambda p, t: NS(summary=lambda: "kotu", passed=False))
    rc3 = cli._cmd_quality(NS(package=str(f)))
    assert rc3 == 1


def test_publish_paths(capsys, monkeypatch, tmp_path):
    import core.aur_publish as AP
    rc = cli._cmd_publish(NS(package=str(tmp_path / "yok.zst"), output_dir=None, aur_url=None))
    assert rc == 1 and "bulunamadı" in capsys.readouterr().out

    f = tmp_path / "p.pkg.tar.zst"
    f.write_bytes(b"x")
    aur_pkg = NS(pkgbuild=tmp_path / "PKGBUILD", srcinfo=tmp_path / ".SRCINFO",
                 name="demo")
    (tmp_path / ".SRCINFO").write_text("pkgname=demo")
    monkeypatch.setattr(AP, "prepare_aur_package",
                        lambda p, o: (True, "hazir", aur_pkg))
    rc2 = cli._cmd_publish(NS(package=str(f), output_dir=None, aur_url=None))
    out = capsys.readouterr().out
    assert rc2 == 0 and "PKGBUILD" in out and ".SRCINFO" in out

    monkeypatch.setattr(AP, "prepare_aur_package", lambda p, o: (False, "kirik", None))
    rc3 = cli._cmd_publish(NS(package=str(f), output_dir=None, aur_url=None))
    assert rc3 == 1 and "kirik" in capsys.readouterr().out


def test_publish_push_to_aur(capsys, monkeypatch, tmp_path):
    import core.aur_publish as AP
    f = tmp_path / "p.pkg.tar.zst"
    f.write_bytes(b"x")
    aur_pkg = NS(pkgbuild=tmp_path / "sub" / "PKGBUILD",
                 srcinfo=tmp_path / "sub" / ".SRCINFO", name="demo")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / ".SRCINFO").write_text("x")
    monkeypatch.setattr(cli, "discover_tools", _tools)
    monkeypatch.setattr(AP, "prepare_aur_package", lambda p, o: (True, "hazir", aur_pkg))
    monkeypatch.setattr(AP, "push_to_aur", lambda d, u: (True, "itildi"))
    rc = cli._cmd_publish(NS(package=str(f), output_dir=None,
                             aur_url="ssh://aur/x.git"))
    out = capsys.readouterr().out
    assert rc == 0 and "itildi" in out


def test_verify_rollback_cli(capsys, monkeypatch):
    import core.rollback_verify as RV
    monkeypatch.setattr(RV, "verify_rollback",
                        lambda: NS(verified=True, backend="btrfs",
                                   snapshot_name="sn", detail="✅ tamam",
                                   files_checked=3))
    rc = cli._cmd_verify_rollback(NS())
    out = capsys.readouterr().out
    assert rc == 0 and "tamam" in out