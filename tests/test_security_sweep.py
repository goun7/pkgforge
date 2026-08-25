"""Coverage itmesi - core/security.py: bomba taramasi, imzalar, sandbox."""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from core import security as SEC
from core.security import (
    _ELF_SUSPICIOUS_PATTERNS,
    _elf_has_suspicious_pattern,
    _looks_like_elf,
    _safe_resolve,
    build_sandbox_cmd,
    check_compression_bomb,
    run_sandboxed,
    verify_deb_signature,
    verify_rpm_signature,
)


def _big_file(tmp_path: Path, name="buyuk.deb", kb=220) -> Path:
    p = tmp_path / name
    p.write_bytes(b"0" * (kb * 1024))
    return p


@pytest.fixture()
def fake_tools():
    return NS(ar="/usr/bin/ar", bsdtar="/usr/bin/bsdtar",
              rpm2cpio="/usr/bin/rpm2cpio", gpg="/usr/bin/gpg")


def test_bomb_missing_archive_returns_none(tmp_path):
    assert check_compression_bomb(tmp_path / "yok.deb", NS()) is None


def test_bomb_tiny_archive_returns_none(fake_tools, tmp_path):
    small = tmp_path / "kucuk.deb"
    small.write_bytes(b"x" * 1024)
    assert check_compression_bomb(small, fake_tools) is None


def test_bomb_deb_flow_warns_on_high_ratio(fake_tools, tmp_path, monkeypatch):
    def fake_safe_run(cmd, timeout=0, input=None):
        sub = cmd[1:2]
        if sub == ["t"]:
            return NS(returncode=0, stdout="debian-binary\ndata.tar.xz")
        if sub == ["p"]:
            return NS(returncode=0, stdout="payload")
        return NS(returncode=0,
                  stdout="\n".join(f"f{i}" for i in range(120)))
    monkeypatch.setattr(SEC, "safe_run", fake_safe_run)
    big = _big_file(tmp_path)
    warn = check_compression_bomb(big, fake_tools, max_ratio=5)
    assert warn and "decompression bomb" in warn


@pytest.mark.parametrize("step", ["ar_t_fail", "no_data_tar",
                                  "ar_p_fail", "bsdtar_fail", "few_members"])
def test_bomb_deb_safe_exits(fake_tools, tmp_path, monkeypatch, step):
    def fake_safe_run(cmd, timeout=0, input=None):
        sub = cmd[1:2]
        if step == "ar_t_fail":
            return NS(returncode=1, stdout="")
        if sub == ["t"]:
            if step == "no_data_tar":
                return NS(returncode=0, stdout="debian-binary")
            return NS(returncode=0, stdout="data.tar.xz")
        if sub == ["p"]:
            if step == "ar_p_fail":
                return NS(returncode=2, stdout="")
            return NS(returncode=0, stdout="payload")
        if step == "bsdtar_fail":
            return NS(returncode=1, stdout="")
        return NS(returncode=0,
                  stdout="\n".join(f"f{i}" for i in range(3)))
    monkeypatch.setattr(SEC, "safe_run", fake_safe_run)
    big = _big_file(tmp_path)
    assert check_compression_bomb(big, fake_tools, max_ratio=2) is None


def test_bomb_deb_scanner_crash_swallowed(fake_tools, tmp_path, monkeypatch):
    def boom(cmd, timeout=0, input=None):
        raise RuntimeError("arac patladi")
    monkeypatch.setattr(SEC, "safe_run", boom)
    big = _big_file(tmp_path)
    assert check_compression_bomb(big, fake_tools) is None


def test_bomb_rpm_flow_warns(fake_tools, tmp_path, monkeypatch):
    def fake_safe_run(cmd, timeout=0, input=None):
        return NS(returncode=0, stdout="104857600\n51200\n")
    monkeypatch.setattr(SEC, "safe_run", fake_safe_run)
    big = _big_file(tmp_path, "paket.rpm")
    warn = check_compression_bomb(big, fake_tools, max_ratio=100)
    assert warn and "kurulum boyutu" in warn


def test_bomb_rpm_tool_fail_quiet(fake_tools, tmp_path, monkeypatch):
    monkeypatch.setattr(SEC, "safe_run",
                        lambda cmd, timeout=0, input=None:
                        NS(returncode=1, stdout=""))
    big = _big_file(tmp_path, "paket.rpm")
    assert check_compression_bomb(big, fake_tools) is None


def test_deb_signature_without_tools():
    res = verify_deb_signature(Path("/x.deb"), NS(ar="", gpg=""))
    assert res.has_signature is False and "bulunamadı" in res.detail


def test_deb_signature_unsigned(fake_tools, tmp_path, monkeypatch):
    monkeypatch.setattr(SEC.subprocess, "run",
                        lambda *a, **k: NS(returncode=0, stdout="usr/bin/x"))
    res = verify_deb_signature(tmp_path / "a.deb", fake_tools)
    assert res.has_signature is False and "imzasız" in res.detail


def test_deb_signature_member_found(fake_tools, tmp_path, monkeypatch):
    monkeypatch.setattr(SEC.subprocess, "run",
                        lambda *a, **k: NS(returncode=0,
                                           stdout="_gpgorigin\nusr/bin"))
    res = verify_deb_signature(tmp_path / "a.deb", fake_tools)
    assert res.has_signature is True and "_gpgorigin" in res.detail


def test_deb_signature_tool_timeout(fake_tools, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired("ar", 10)
    monkeypatch.setattr(SEC.subprocess, "run", boom)
    res = verify_deb_signature(tmp_path / "a.deb", fake_tools)
    assert "basarisiz" in res.detail or "başarısız" in res.detail


_RPM_BASE = b"\xed\xab\xee\xdb" + b"\x00" * 92


def test_rpm_signature_bad_magic(tmp_path):
    f = tmp_path / "x.rpm"
    f.write_bytes(b"NOPE" + b"\x00" * 92)
    res = verify_rpm_signature(f, NS())
    assert "magic" in res.detail


def test_rpm_signature_present(tmp_path):
    f = tmp_path / "x.rpm"
    f.write_bytes(_RPM_BASE[:5] + b"\x05" + _RPM_BASE[6:])
    res = verify_rpm_signature(f, NS())
    assert res.has_signature is True


def test_rpm_signature_absent(tmp_path):
    f = tmp_path / "x.rpm"
    f.write_bytes(_RPM_BASE)
    res = verify_rpm_signature(f, NS())
    assert res.has_signature is False


def test_rpm_signature_unreadable(tmp_path):
    res = verify_rpm_signature(tmp_path / "yok.rpm", NS())
    assert "başarısız" in res.detail or "basarisiz" in res.detail


def test_safe_resolve_survives_symlink_loop(tmp_path):
    loop = tmp_path / "dongu"
    loop.symlink_to(loop)
    out = _safe_resolve(loop / "icinde")
    assert isinstance(out, Path)


def test_elf_helpers_and_suspicion(tmp_path):
    elf = tmp_path / "bin"
    pattern = _ELF_SUSPICIOUS_PATTERNS[0]
    elf.write_bytes(b"\x7fELF" + bytes(pattern))
    assert _looks_like_elf(elf) is True
    assert _elf_has_suspicious_pattern(elf, 4096) is True
    plain = tmp_path / "duz"
    plain.write_bytes(b"MZ degil")
    assert _looks_like_elf(plain) is False


def test_elf_helpers_oserror_paths(tmp_path):
    kilitli = tmp_path / "kilitli"
    kilitli.write_bytes(b"\x7fELFxxxx")
    kilitli.chmod(0o000)
    try:
        assert _looks_like_elf(kilitli) is False
        assert _elf_has_suspicious_pattern(kilitli, 64) is False
    finally:
        kilitli.chmod(0o644)


def test_build_sandbox_cmd_without_bwrap():
    prog, args = build_sandbox_cmd(["makepkg", "-f"], Path("/w"),
                                   NS(bwrap=""))
    assert prog == "makepkg" and args == ["-f"]


def test_build_sandbox_cmd_merged_dir_variants(monkeypatch, tmp_path):
    tools = NS(bwrap="/usr/bin/bwrap")
    links = {"/bin": True, "/sbin": True}
    monkeypatch.setattr(SEC.os.path, "islink",
                        lambda p: links.get(p, False))
    monkeypatch.setattr(SEC.os.path, "realpath",
                        lambda p: "/mnt/sbin-gercek" if p == "/sbin" else p)
    dirs = {"/lib": True}
    monkeypatch.setattr(SEC.os.path, "isdir",
                        lambda p: dirs.get(p, False))
    real_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: False)
    prog, args = build_sandbox_cmd(["echo", "hi"], tmp_path, tools)
    monkeypatch.setattr(Path, "exists", real_exists)
    assert prog == "/usr/bin/bwrap"
    # /bin ve /sbin symlink ama hedefleri /usr altinda degil -> ro-bind dali
    # (merged_dir baglanir); /lib gercek dizin -> isdir ro-bind dali.
    assert "--symlink" not in args
    for d in ("/bin", "/sbin", "/lib"):
        assert d in args


def test_build_sandbox_cmd_extra_binds_and_network(tmp_path):
    tools = NS(bwrap="/usr/bin/bwrap")
    ekstra = tmp_path / "ekstra"
    ekstra.mkdir()
    yok = tmp_path / "yok"
    _prog, args = build_sandbox_cmd(
        ["ls"], tmp_path, tools,
        allow_network=True, extra_ro_binds=[ekstra, yok])
    assert "--unshare-net" not in args
    assert str(ekstra) in args


def test_run_sandboxed_uses_bwrap(tmp_path, monkeypatch):
    sent = {}
    def fake_run(cmd, **kw):
        sent["cmd"] = list(cmd)
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(SEC.subprocess, "run", fake_run)
    tools = NS(bwrap="/usr/bin/bwrap")
    run_sandboxed(["true"], tmp_path, tools)
    assert sent["cmd"][0] == "/usr/bin/bwrap"


def test_run_sandboxed_direct_fallback(tmp_path, monkeypatch):
    sent = {}
    def fake_run(cmd, **kw):
        sent.update(cmd=list(cmd), kw=dict(kw))
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(SEC.subprocess, "run", fake_run)
    tools = NS(bwrap="")
    run_sandboxed(["echo", "selam"], tmp_path, tools)
    assert sent["cmd"] == ["echo", "selam"]
    assert sent["kw"]["cwd"] == str(tmp_path)
