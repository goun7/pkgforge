"""Round-65: mutmut killer testleri — core/security.py.

Gevsek assert'lerin (any(...), len==N) hayatta biraktigi mutantlari oldurmek
icin KESIN deger/mesaj/sinir assert'leri + subprocess-mock kapsama ekler
(validate_mime_type, safe_run, run_sandboxed onceki secimde 'no tests' idi).
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import core.security as SEC
from config import ToolPaths


# ── is_valid_package_name: 128 siniri ────────────────────────────
def test_pkg_name_128_ok_129_bad():
    assert SEC.is_valid_package_name("a" * 128) is True
    assert SEC.is_valid_package_name("a" * 129) is False


def test_pkg_name_exact_charset():
    # '-' ortada gecerli, basta gecersiz; bos tek karakter gecersiz
    assert SEC.is_valid_package_name("a-b") is True
    assert SEC.is_valid_package_name("-a") is False
    assert SEC.is_valid_package_name("a" * 1) is True


# ── validate_file_size: kesin sinir + tam mesaj ──────────────────
def _mk(tmp_path: Path, nbytes: int) -> Path:
    p = tmp_path / f"f{nbytes}.bin"
    with open(p, "wb") as fh:
        fh.write(b"x" * nbytes)
    return p


def test_file_size_exact_warn_returns_none(tmp_path):
    MB = 1024 * 1024
    p = _mk(tmp_path, MB)  # tam 1 MB -> 1.0 > 1 False
    assert SEC.validate_file_size(p, max_mb=10, warn_mb=1) is None


def test_file_size_just_over_warn_exact_msg(tmp_path):
    MB = 1024 * 1024
    p = _mk(tmp_path, MB + 1)  # ~1.0000009 MB -> ':.0f' = '1'
    assert SEC.validate_file_size(p, max_mb=10, warn_mb=1) == "Dosya boyutu büyük: 1 MB"


def test_file_size_exact_max_no_raise(tmp_path):
    MB = 1024 * 1024
    p = _mk(tmp_path, MB)  # tam 1 MB -> 1.0 > 1 False (raise olmaz)
    assert SEC.validate_file_size(p, max_mb=1, warn_mb=10) is None


def test_file_size_over_max_exact_msg(tmp_path):
    MB = 1024 * 1024
    p = _mk(tmp_path, 2 * MB)
    with pytest.raises(ValueError) as ei:
        SEC.validate_file_size(p, max_mb=1, warn_mb=1)
    assert "Dosya boyutu (2 MB) maksimum limiti aşıyor (1 MB)." in str(ei.value)


# ── check_path_traversal: kesin icerik ───────────────────────────
def test_path_traversal_exact_offending():
    assert SEC.check_path_traversal(["../etc/passwd"]) == ["../etc/passwd"]
    assert SEC.check_path_traversal(["usr/bin/ok", "../evil"]) == ["../evil"]
    assert SEC.check_path_traversal(["/home/u/.ssh/k"]) == ["/home/u/.ssh/k"]


def test_path_traversal_fhs_and_edge():
    assert SEC.check_path_traversal(["/usr/bin/app"]) == []
    assert SEC.check_path_traversal(["/etc/app.conf"]) == []
    assert SEC.check_path_traversal(["/usr"]) == []          # tek FHS kok
    assert SEC.check_path_traversal(["./usr/share/x"]) == []  # ./ oneki


# ── _safe_resolve: kesin sonuc ───────────────────────────────────
def test_safe_resolve_normalizes_dotdot(tmp_path):
    base = tmp_path / "a"
    base.mkdir()
    assert SEC._safe_resolve(base / "b" / "..") == SEC._safe_resolve(base)


def test_safe_resolve_fallback_lexical(monkeypatch):
    p = Path("/a/b/../c")
    def boom(self, strict=False):
        raise OSError("cannot traverse")
    monkeypatch.setattr(Path, "resolve", boom)
    assert SEC._safe_resolve(p) == Path("/a/c")


# ── check_symlink_attacks: kesin format ──────────────────────────
def test_symlink_escape_exact_entry(tmp_path):
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "evil").symlink_to("/home/user/.ssh/id_rsa")
    got = SEC.check_symlink_attacks(root)
    assert got == [f"{root / 'evil'} → /home/user/.ssh/id_rsa"]


def test_symlink_relative_escape_exact(tmp_path):
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "esc").symlink_to("../../etc/passwd")
    got = SEC.check_symlink_attacks(root)
    assert len(got) == 1 and got[0].endswith("→ ../../etc/passwd")


# ── check_dangerous_files: tam mesajlar ──────────────────────────
def test_dangerous_setuid_exact(tmp_path):
    f = tmp_path / "suid.bin"
    f.write_bytes(b"notelf")
    os.chmod(f, 0o4755)
    errors, warnings = SEC.check_dangerous_files(tmp_path)
    assert errors == []
    assert warnings == ["setuid/setgid: suid.bin (mode 0o4755)"]


def test_dangerous_world_writable_exact(tmp_path):
    f = tmp_path / "ww.txt"
    f.write_bytes(b"hi")
    os.chmod(f, 0o666)
    errors, warnings = SEC.check_dangerous_files(tmp_path)
    assert errors == []
    assert warnings == ["world-writable: ww.txt"]


def test_dangerous_fifo_exact(tmp_path):
    os.mkfifo(tmp_path / "pipe")
    errors, warnings = SEC.check_dangerous_files(tmp_path)
    assert errors == ["device/fifo/socket node: pipe"]
    assert warnings == []


def test_dangerous_suspicious_elf_exact(tmp_path):
    f = tmp_path / "evil.elf"
    f.write_bytes(bytes([0x7f, 0x45, 0x4c, 0x46]) + b"\x00" * 40 + b"/bin/sh -i")
    os.chmod(f, 0o755)
    errors, warnings = SEC.check_dangerous_files(tmp_path)
    assert errors == []
    assert warnings == ["suspicious-elf: evil.elf"]


# ── sha256_hash: bilinen deger ───────────────────────────────────
def test_sha256_known_value(tmp_path):
    p = tmp_path / "h.bin"
    p.write_bytes(b"hello world")
    assert SEC.sha256_hash(p) == hashlib.sha256(b"hello world").hexdigest()
    assert SEC.sha256_hash(p) == (
        "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )


def test_sha256_empty(tmp_path):
    p = tmp_path / "e.bin"
    p.write_bytes(b"")
    assert SEC.sha256_hash(p) == hashlib.sha256(b"").hexdigest()


# ── validate_mime_type (subprocess mock) ─────────────────────────
def test_mime_valid_deb(monkeypatch, tmp_path):
    f = tmp_path / "p.deb"
    f.write_bytes(b"x")
    monkeypatch.setattr(
        SEC.subprocess, "run",
        lambda cmd, **kw: NS(stdout="application/vnd.debian.binary-package\n",
                             returncode=0))
    assert SEC.validate_mime_type(f, ToolPaths(file_cmd="/usr/bin/file")) == (
        "application/vnd.debian.binary-package")


def test_mime_valid_rpm(monkeypatch, tmp_path):
    f = tmp_path / "p.rpm"
    f.write_bytes(b"x")
    monkeypatch.setattr(SEC.subprocess, "run",
                        lambda cmd, **kw: NS(stdout="application/x-rpm\n", returncode=0))
    assert SEC.validate_mime_type(f, ToolPaths(file_cmd="/usr/bin/file")) == "application/x-rpm"


def test_mime_invalid_raises(monkeypatch, tmp_path):
    f = tmp_path / "p.txt"
    f.write_bytes(b"x")
    monkeypatch.setattr(SEC.subprocess, "run",
                        lambda cmd, **kw: NS(stdout="text/plain\n", returncode=0))
    with pytest.raises(ValueError) as ei:
        SEC.validate_mime_type(f, ToolPaths(file_cmd="/usr/bin/file"))
    assert "Geçersiz dosya türü: text/plain" in str(ei.value)


def test_mime_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        SEC.validate_mime_type(tmp_path / "yok.deb", ToolPaths(file_cmd="/usr/bin/file"))


# ── safe_run (subprocess mock) ───────────────────────────────────
def test_safe_run_text_autodetect(monkeypatch):
    seen = []
    def fake_run(cmd, **kw):
        seen.append(kw)
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(SEC.subprocess, "run", fake_run)
    SEC.safe_run(["echo"])
    assert seen[-1]["text"] is True          # input None -> text
    SEC.safe_run(["echo"], input=b"bytes")
    assert seen[-1]["text"] is False         # bytes input -> binary
    SEC.safe_run(["echo"], input="str")
    assert seen[-1]["text"] is True          # str input -> text
    SEC.safe_run(["echo"], text=False)
    assert seen[-1]["text"] is False         # explicit override


def test_safe_run_cwd_and_timeout(monkeypatch, tmp_path):
    seen = []
    def fake_run(cmd, **kw):
        seen.append(kw)
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(SEC.subprocess, "run", fake_run)
    SEC.safe_run(["ls"], cwd=tmp_path, timeout=7)
    assert seen[-1]["cwd"] == str(tmp_path)
    assert seen[-1]["timeout"] == 7
    SEC.safe_run(["ls"])
    assert seen[-1]["cwd"] is None


# ── run_sandboxed (subprocess mock) ──────────────────────────────
def test_run_sandboxed_uses_bwrap(monkeypatch, tmp_path):
    calls = []
    def fake_run(cmd, **kw):
        calls.append(cmd)
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(SEC.subprocess, "run", fake_run)
    SEC.run_sandboxed(["echo", "hi"], tmp_path, ToolPaths(bwrap="/usr/bin/bwrap"))
    assert calls[0][0] == "/usr/bin/bwrap"
    assert calls[0][-2:] == ["echo", "hi"]


def test_run_sandboxed_fallback_direct(monkeypatch, tmp_path):
    calls = []
    def fake_run(cmd, **kw):
        calls.append((cmd, kw.get("cwd")))
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(SEC.subprocess, "run", fake_run)
    SEC.run_sandboxed(["echo", "hi"], tmp_path, ToolPaths(bwrap=""))
    assert calls[0][0] == ["echo", "hi"]
    assert calls[0][1] == str(tmp_path)
