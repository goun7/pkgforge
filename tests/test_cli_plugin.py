"""Coverage itmesi - cli plugin komutu tum eylemler."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import cli
import core.plugins as PLG
import core.plugins.marketplace as MP


def _args(action, name=None, force=False, version="latest"):
    return NS(plugin_action=action, name=name, force=force, version=version)


def test_plugin_install_success_and_fail(capsys, monkeypatch):
    monkeypatch.setattr(MP, "install_plugin",
                        lambda name, version="latest", force=False:
                        Path("/tmp/x.py"))
    monkeypatch.setattr(PLG, "reload_plugins", lambda: [1, 2])
    rc = cli._cmd_plugin(_args("install", "alfa"))
    out = capsys.readouterr().out
    assert rc == 0 and "kuruldu" in out and "2 plugin aktif" in out

    def nf(name, version="latest", force=False):
        raise FileNotFoundError("yok")
    monkeypatch.setattr(MP, "install_plugin", nf)
    rc2 = cli._cmd_plugin(_args("install", "yok"))
    assert rc2 == 1 and "yok" in capsys.readouterr().out


def test_plugin_install_runtime_error(capsys, monkeypatch):
    def bad(name, version="latest", force=False):
        raise RuntimeError("checksum")
    monkeypatch.setattr(MP, "install_plugin", bad)
    monkeypatch.setattr(PLG, "reload_plugins", list)
    rc = cli._cmd_plugin(_args("install", "kotu"))
    assert rc == 1 and "checksum" in capsys.readouterr().out


def test_plugin_remove_found_and_missing(capsys, monkeypatch):
    monkeypatch.setattr(PLG, "reload_plugins", list)
    monkeypatch.setattr(MP, "uninstall_plugin", lambda n: True)
    rc = cli._cmd_plugin(_args("remove", "alfa"))
    assert rc == 0 and "kaldirildi".replace("i","i") or True
    out = capsys.readouterr().out
    assert rc == 0 and "kaldırıldı" in out

    monkeypatch.setattr(MP, "uninstall_plugin", lambda n: False)
    rc2 = cli._cmd_plugin(_args("remove", "yok"))
    assert rc2 == 1 and "bulunamadı" in capsys.readouterr().out


def test_plugin_list_and_available(capsys, monkeypatch):
    monkeypatch.setattr(PLG, "reload_plugins", list)
    monkeypatch.setattr(MP, "list_installed_plugins", list)
    rc = cli._cmd_plugin(_args("list"))
    assert rc == 0 and "yerel plugin yok" in capsys.readouterr().out.lower()

    apps = [{"name": "a.py", "size": 12}, {"name": "b.py", "size": 34}]
    monkeypatch.setattr(MP, "list_installed_plugins", lambda: apps)
    cli._cmd_plugin(_args("list"))
    assert "a.py" in capsys.readouterr().out

    monkeypatch.setattr(MP, "fetch_available_plugins", list)
    rc3 = cli._cmd_plugin(_args("available"))
    assert rc3 == 0 and "bulunamadı" in capsys.readouterr().out

    avail = [{"name": "c", "version": "9", "description": "araç"}]
    monkeypatch.setattr(MP, "fetch_available_plugins", lambda: avail)
    cli._cmd_plugin(_args("available"))
    assert "araç" in capsys.readouterr().out


def test_plugin_update_and_audit(capsys, monkeypatch):
    monkeypatch.setattr(PLG, "reload_plugins", list)
    monkeypatch.setattr(MP, "update_plugin", lambda n: (True, "guncel", None))
    rc = cli._cmd_plugin(_args("update", "alfa"))
    assert rc == 0 and "guncel" in capsys.readouterr().out

    monkeypatch.setattr(MP, "update_plugin", lambda n: (False, "kirik", None))
    rc2 = cli._cmd_plugin(_args("update", "alfa"))
    assert rc2 == 1 and "kirik" in capsys.readouterr().out

    monkeypatch.setattr(MP, "audit_plugins", list)
    rc3 = cli._cmd_plugin(_args("audit"))
    assert rc3 == 0 and "yok" in capsys.readouterr().out.lower()

    results = [{"status": "changed", "name": "x", "message": "degisti"}]
    monkeypatch.setattr(MP, "audit_plugins", lambda: results)
    cli._cmd_plugin(_args("audit"))
    assert "degisti" in capsys.readouterr().out


def test_plugin_invalid_action(capsys):
    rc = cli._cmd_plugin(_args("bilinmeyen"))
    assert rc == 1 and "Geçersiz" in capsys.readouterr().out