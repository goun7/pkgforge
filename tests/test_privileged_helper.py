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


# --- Faz 14: write-batch (tek pkexec diyaloğunda çoklu yazma) -----------------

def test_write_batch_manifest_roundtrip_and_argv():
    from core.privileged import (
        build_write_batch_manifest,
        privileged_write_batch_argv,
    )
    m = build_write_batch_manifest([
        ("755", "/usr/local/bin/a.sh", "#!/bin/bash\necho A"),
        ("644", "/etc/systemd/system/b.service", "[Unit]"),
    ])
    # Üçlü NUL-ayırıcılı: 6 alan + sonda kapanış NUL'u
    assert m.count(b"\x00") == 6
    argv = privileged_write_batch_argv("pkexec")
    assert argv[2:] == ["write-batch"]


def test_helper_write_batch_writes_all_files(tmp_path):
    """Gerçek write-batch mantığı (parse/atomik yazma/chmod/sayaç) hermetik
    sınanır: betiğin bir kopyasında izinli prefix tmp_path'e yönlendirilir —
    test sistemi /usr/local/bin'e yazamaz (sandbox/CI paritesi)."""
    import os

    from core.privileged import build_write_batch_manifest

    # tmp kopya + prefix yönlendirme
    src = HELPER.read_text()
    assert 'ALLOWED_WRITE_PREFIXES=' in src
    patched = src.replace(
        'ALLOWED_WRITE_PREFIXES=("/etc/systemd/system/" "/usr/local/bin/" "/usr/share/pkgforge/")',
        f'ALLOWED_WRITE_PREFIXES=("{tmp_path}/")',
    )
    assert patched != src, "prefix satırı bulunamadı"
    helper2 = tmp_path / "helper-test.sh"
    helper2.write_text(patched)

    hedef1 = tmp_path / "wb-a.sh"
    hedef2 = tmp_path / "wb-b.service"
    manifest = build_write_batch_manifest([
        ("755", str(hedef1), "#!/bin/bash\necho A"),
        ("644", str(hedef2), "[Unit]\nB"),
    ])
    r = subprocess.run(
        ["bash", str(helper2), "write-batch"], input=manifest,
        capture_output=True, check=False, timeout=15)
    assert r.returncode == 0, r.stderr
    assert b"2 dosya yazildi" in r.stdout
    assert hedef1.read_text().endswith("echo A")
    assert hedef2.read_text() == "[Unit]\nB"
    # modlar uygulandi mi
    assert (os.stat(hedef1).st_mode & 0o777) == 0o755
    assert (os.stat(hedef2).st_mode & 0o777) == 0o644


def test_helper_write_batch_rejects_bad_path(tmp_path):
    from core.privileged import build_write_batch_manifest

    manifest = build_write_batch_manifest([
        ("644", "/root/evil", "x"),
    ])
    r = subprocess.run(
        ["bash", str(HELPER), "write-batch"], input=manifest,
        capture_output=True, check=False, timeout=15)
    assert r.returncode == 6
    assert b"izin verilen dizinlerde degil" in r.stderr


# --- S3: argv validasyon matrisleri (privileged.py raise dallari) ---------

def test_unit_name_validation_matrix():
    from core.privileged import _check_unit_name

    _check_unit_name("pkgforge-auto-update.timer")  # gecerli
    for kotu in ("", "a;b", "x y", "u$nit", "../x"):
        with pytest.raises(ValueError):
            _check_unit_name(kotu)


def test_snapshot_argv_rejects_bad_op():
    from core.privileged import privileged_snapshot_argv

    with pytest.raises(ValueError, match="snapshot islemi"):
        privileged_snapshot_argv("pkexec", "format-c:", "/")


def test_snapshot_argv_rejects_bad_target():
    from core.privileged import privileged_snapshot_argv

    with pytest.raises(ValueError, match="hedef"):
        privileged_snapshot_argv("pkexec", "take-btrfs", "")
    with pytest.raises(ValueError, match="hedef"):
        privileged_snapshot_argv("pkexec", "take-btrfs", "../kacis")
    with pytest.raises(ValueError, match="hedef"):
        privileged_snapshot_argv("pkexec", "take-btrfs", "relatif/yol")


def test_snapshot_argv_zfs_shape_rules():
    from core.privileged import privileged_snapshot_argv

    with pytest.raises(ValueError, match="dataset@snap"):
        privileged_snapshot_argv("pkexec", "take-zfs", "havuz")
    with pytest.raises(ValueError, match="dataset"):
        privileged_snapshot_argv("pkexec", "take-zfs", "havuz$@snap")
    with pytest.raises(ValueError, match="pkgforge-"):
        privileged_snapshot_argv("pkexec", "take-zfs", "havuz@diger-ad")
    ok = privileged_snapshot_argv("pkexec", "take-zfs", "havuz/ds@pkgforge-01")
    assert ok[0] == "pkexec" and "take-zfs" in ok


def test_install_pkg_argv_snapshot_flag():
    from core.privileged import privileged_install_pkg_argv

    argv = privileged_install_pkg_argv("pkexec", "/tmp/x.pkg.tar.zst",
                                       snapshot="snap-1")
    assert argv[-3:] == ["--snapshot", "snap-1", "/tmp/x.pkg.tar.zst"]
    argv2 = privileged_install_pkg_argv("pkexec", "/tmp/x.pkg.tar.zst")
    assert "--snapshot" not in argv2
