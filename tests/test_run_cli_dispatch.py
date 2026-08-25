"""Coverage itmesi - run_cli dispatch tablosu."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

import cli

DISPATCH = [
    ("convert", "_cmd_convert"), ("list", "_cmd_list"),
    ("remove", "_cmd_remove"), ("rollback", "_cmd_rollback"),
    ("check-updates", "_cmd_check_updates"),
    ("flatpak-export", "_cmd_flatpak_export"),
    ("appimage-export", "_cmd_appimage_export"),
    ("rpm-to-deb", "_cmd_rpm_to_deb"), ("provenance", "_cmd_provenance"),
    ("benchmark", "_cmd_benchmark"), ("sign", "_cmd_sign"),
    ("verify", "_cmd_verify"), ("sbom", "_cmd_sbom"),
    ("attest", "_cmd_attest"), ("graph", "_cmd_graph"),
    ("audit", "_cmd_audit"), ("scan-image", "_cmd_scan_image"),
    ("from-source", "_cmd_from_source"), ("abi-check", "_cmd_abi_check"),
    ("health", "_cmd_health"), ("doctor", "_cmd_doctor"),
    ("wrapped", "_cmd_wrapped"), ("snapshot-cleanup", "_cmd_snapshot_cleanup"),
    ("quality", "_cmd_quality"), ("publish", "_cmd_publish"),
    ("verify-rollback", "_cmd_verify_rollback"), ("plugin", "_cmd_plugin"),
    ("delta", "_cmd_delta"), ("completion", "_cmd_completion"),
]


@pytest.mark.parametrize("command,handler", DISPATCH)
def test_dispatch_routes_to_handler(monkeypatch, command, handler):
    seen = []
    monkeypatch.setattr(cli, handler, lambda a, _s=seen: _s.append(a) or 7)
    args = NS(command=command)
    rc = cli.run_cli(args)
    assert rc == 7 and seen == [args]


def test_dispatch_invalid_command(capsys):
    rc = cli.run_cli(NS(command="yok-boyle"))
    assert rc == 1 and "geçersiz" in capsys.readouterr().out.lower()