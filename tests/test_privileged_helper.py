"""Faz 5 (F5.4) — konsolide yetkili yardimci + komut ureticileri."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core.privileged import (
    PRIVILEGED_HELPER,
    privileged_chmod_argv,
    privileged_remove_argv,
    privileged_systemctl_argv,
    privileged_write_argv,
)

HELPER = Path(__file__).resolve().parent.parent / "scripts" / "pkgforge-privileged.sh"


# --- komut uretici (birim) testleri --------------------------------------

def test_helper_script_exists_and_executable():
    assert HELPER.is_file()
    assert PRIVILEGED_HELPER == HELPER


def test_write_argv_shape():
    argv = privileged_write_argv("pkexec", "/etc/systemd/system/x.service")
    assert argv[0] == "pkexec"
    assert argv[1] == str(HELPER)
    assert argv[2:] == ["write-file", "/etc/systemd/system/x.service"]


def test_chmod_argv_shape():
    argv = privileged_chmod_argv("pkexec", "755", "/usr/local/bin/x.sh")
    assert argv[2:] == ["chmod", "755", "/usr/local/bin/x.sh"]


def test_remove_argv_shape():
    argv = privileged_remove_argv("pkexec", "/etc/systemd/system/x.timer")
    assert argv[2:] == ["remove-file", "/etc/systemd/system/x.timer"]


def test_systemctl_argv_with_unit():
    argv = privileged_systemctl_argv("pkexec", "enable", "x.timer")
    assert argv[2:] == ["systemctl", "enable", "x.timer"]


def test_systemctl_argv_daemon_reload_no_unit():
    argv = privileged_systemctl_argv("pkexec", "daemon-reload")
    assert argv[2:] == ["systemctl", "daemon-reload"]


def test_systemctl_rejects_unknown_verb():
    with pytest.raises(ValueError):
        privileged_systemctl_argv("pkexec", "reboot", "x")


# --- helper script dogrulama (bash ile calistir) testleri ----------------

def _run_helper(args, stdin=""):
    return subprocess.run(
        ["bash", str(HELPER), *args], input=stdin,
        capture_output=True, text=True, check=False, timeout=15)


def test_helper_usage_on_no_args():
    r = _run_helper([])
    assert r.returncode == 1
    assert "Kullanim" in r.stderr


def test_helper_rejects_write_traversal():
    r = _run_helper(["write-file", "/etc/systemd/system/../../etc/passwd"], "x")
    assert r.returncode == 5
    assert "traversal" in r.stderr


def test_helper_rejects_write_outside_allowed_prefix():
    r = _run_helper(["write-file", "/root/evil"], "x")
    assert r.returncode == 6


def test_helper_rejects_relative_write_path():
    r = _run_helper(["write-file", "etc/systemd/system/x"], "x")
    assert r.returncode == 2


def test_helper_rejects_bad_chmod_mode():
    r = _run_helper(["chmod", "9999", "/usr/local/bin/x"])
    assert r.returncode == 7


def test_helper_rejects_bad_systemctl_verb():
    r = _run_helper(["systemctl", "reboot"])
    assert r.returncode == 8


def test_helper_rejects_shell_metachar_unit():
    r = _run_helper(["systemctl", "enable", "bad;rm -rf /"])
    assert r.returncode == 9


def test_helper_install_pkg_rejects_bad_extension(tmp_path):
    fake = tmp_path / "evil.txt"
    fake.write_text("x")
    r = _run_helper(["install-pkg", str(fake)])
    assert r.returncode == 4
