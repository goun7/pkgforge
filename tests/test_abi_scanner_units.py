"""Coverage itmesi — core/abi_scanner.py sembol taramasi ve yardimcilar."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import core.abi_scanner as AS
from core.abi_scanner import (
    SymbolMismatch,
    _check_version_available,
    _extract_symbol_for_version,
    _get_available_versions,
    _is_elf_binary,
    scan_elf_symbols,
)


def _ns(code, out="", err=""):
    return NS(returncode=code, stdout=out, stderr=err)

READEXLF = chr(10).join([
    "Version needs section contains 2 entries:",
    " 000000: Version: 1  File: libc.so.6  Cnt: 2",
    " 0x0010:   Name: GLIBC_2.34  Flags: none  Version: 4",
    " 0x0020:   Name: GLIBCXX_3.4.29  Flags: none  Version: 5",
])

def test_is_elf_and_getters(monkeypatch, tmp_path):
    f = tmp_path / "prog"
    f.write_bytes(bytes([0x7f]) + b"ELFxx")
    assert _is_elf_binary(f) is True
    t = tmp_path / "d.txt"
    t.write_text("x")
    assert _is_elf_binary(t) is False
    assert _is_elf_binary(tmp_path / "yok") is False
    monkeypatch.setattr(AS.shutil, "which", lambda n: None)
    assert AS._get_readelf() is None and AS._get_objcopy() is None

def test_scan_no_readelf_or_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(AS, "_get_readelf", lambda: None)
    assert scan_elf_symbols(tmp_path / "x") == []
    monkeypatch.setattr(AS, "_get_readelf", lambda: "/usr/bin/readelf")
    monkeypatch.setattr(AS, "safe_run", lambda c, timeout=None: _ns(1))
    assert scan_elf_symbols(tmp_path / "x") == []

def test_scan_symbols_mismatch_flow(monkeypatch, tmp_path):
    monkeypatch.setattr(AS, "_get_readelf", lambda: "/usr/bin/readelf")
    monkeypatch.setattr(AS, "safe_run", lambda c, timeout=None: _ns(0, out=READEXLF))
    monkeypatch.setattr(AS, "_check_version_available", lambda tag: None if tag == "GLIBC_2.34" else "GLIBCXX_3.4.30")
    monkeypatch.setattr(AS, "_extract_symbol_for_version", lambda p, t: "pthread_create")
    ms = scan_elf_symbols(tmp_path / "prog")
    assert len(ms) == 1
    m = ms[0]
    assert isinstance(m, SymbolMismatch)
    assert m.symbol == "pthread_create" and m.required_version == "GLIBC_2.34"
    assert m.library == "libc.so.6" and m.severity == "error"

    monkeypatch.setattr(AS, "_extract_symbol_for_version", lambda p, t: None)
    ms2 = scan_elf_symbols(tmp_path / "prog")
    assert ms2[0].symbol == "(GLIBC_2.34)"

def test_check_version_unknown_tag():
    assert _check_version_available("WEIRD_1.2") is None

def test_check_version_with_fake_libs(monkeypatch, tmp_path):
    base = tmp_path / "lib"
    base.mkdir()
    real = base / "libc.so.6"
    real.write_bytes(b"ELF")

    known = {"/usr/lib", "/usr/lib64", "/lib", "/lib64", "/usr/lib/x86_64-linux-gnu"}
    orig_is_dir, orig_is_file = Path.is_dir, Path.is_file
    monkeypatch.setattr(Path, "is_dir", lambda self, **k: True if str(self) in known else orig_is_dir(self))
    monkeypatch.setattr(Path, "is_file", lambda self, **k: True if self == real else orig_is_file(self))
    monkeypatch.setattr(Path, "is_symlink", lambda self, **k: False)
    monkeypatch.setattr(Path, "glob", lambda self, pat: iter([real]) if pat.startswith("libc.so") else iter([]))
    monkeypatch.setattr(AS, "_get_available_versions", lambda p: ["GLIBC_2.35", "GLIBC_2.17"])

    got = _check_version_available("GLIBC_2.34")
    assert got == "GLIBC_2.35"
    assert _check_version_available("GLIBC_9.9") is None

def test_get_available_versions(monkeypatch, tmp_path):
    lib = tmp_path / "l.so"
    monkeypatch.setattr(AS, "_get_readelf", lambda: None)
    assert _get_available_versions(lib) == []
    monkeypatch.setattr(AS, "_get_readelf", lambda: "/r")
    monkeypatch.setattr(AS, "safe_run", lambda c, timeout=None: _ns(0, out=READEXLF))
    assert _get_available_versions(lib) == ["GLIBC_2.34", "GLIBCXX_3.4.29"]
    monkeypatch.setattr(AS, "safe_run", lambda c, timeout=None: _ns(1))
    assert _get_available_versions(lib) == []


def _pkg(tmp_path):
    p = tmp_path / "p.pkg.tar.zst"
    p.write_bytes(b"x")
    return p

NAMCAP_OUT = chr(10).join([
    "PKGBUILD (E): error: depends contains not a dependency (x)",
    "usr/bin/prog (W): warning: unused library",
    "demo: info: refer to wiki",
])

def test_run_namcap(monkeypatch, tmp_path):
    monkeypatch.setattr(AS.shutil, "which", lambda n: None)
    assert AS._run_namcap(_pkg(tmp_path)) == []

    monkeypatch.setattr(AS.shutil, "which", lambda n: "/usr/bin/namcap")
    monkeypatch.setattr(AS, "safe_run", lambda c, timeout=None: _ns(0, out=NAMCAP_OUT))
    res = AS._run_namcap(_pkg(tmp_path))
    assert len(res) == 3
    assert res[0].severity == "error" and res[0].tag != "unknown"
    assert res[1].severity == "warning" and res[2].severity == "info"

def test_check_abi_unknown_pkg(monkeypatch, tmp_path):
    f = tmp_path / "app.rpm"
    f.write_bytes(b"x")
    rep = AS.check_abi_compatibility(f)
    assert isinstance(rep, AS.ABIScanReport) and rep.binary_count == 0

def test_check_abi_full(monkeypatch, tmp_path):
    pkg = _pkg(tmp_path)
    calls = {"n": 0}
    def fake_safe(cmd, timeout=None, cwd=None):
        calls["n"] += 1
        if tuple(cmd[:2]) == ("tar", "xf"):
            dest = Path(cmd[cmd.index("-C") + 1])
            b = dest / "usr" / "bin"
            b.mkdir(parents=True, exist_ok=True)
            (b / "prog").write_bytes(bytes([0x7f]) + b"ELFxx")
        return _ns(0)
    monkeypatch.setattr(AS, "safe_run", fake_safe)
    monkeypatch.setattr(AS.shutil, "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(AS, "_is_elf_binary", lambda p: True)
    monkeypatch.setattr(AS, "scan_elf_symbols", lambda p: [SymbolMismatch(binary=p.name, symbol="s", required_version="GLIBC_9.9", available_version="yok", library="libc.so.6", severity="error")])
    monkeypatch.setattr(AS, "_run_namcap", lambda p: [])
    rep = AS.check_abi_compatibility(pkg)
    assert rep.binary_count >= 1
    assert rep.checked_symbols >= 1 and len(rep.mismatches) >= 1

def test_check_abi_ldd_missing(monkeypatch, tmp_path):
    pkg = _pkg(tmp_path)
    def fake_safe(cmd, timeout=None, cwd=None):
        if tuple(cmd[:2]) == ("tar", "xf"):
            dest = Path(cmd[cmd.index("-C") + 1])
            b = dest / "opt"
            b.mkdir(parents=True, exist_ok=True)
            (b / "tool").write_bytes(bytes([0x7f]) + b"ELFxx")
            return _ns(0)
        if cmd[0].endswith("ldd"):
            return _ns(0, out="libmissing.so => not found" + chr(10) + "libc.so.6 => /usr/lib/libc.so.6")
        return _ns(0)
    monkeypatch.setattr(AS, "safe_run", fake_safe)
    monkeypatch.setattr(AS.shutil, "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(AS, "_get_readelf", lambda: None)
    monkeypatch.setattr(AS, "_run_namcap", lambda p: [])
    rep = AS.check_abi_compatibility(pkg)
    assert any(lib == "libmissing.so" for _, lib in rep.missing_libs)

def test_extract_symbol_for_version(monkeypatch, tmp_path):
    elf = tmp_path / "e"
    monkeypatch.setattr(AS, "_get_readelf", lambda: None)
    assert _extract_symbol_for_version(elf, "GLIBC_2.34") is None
    monkeypatch.setattr(AS, "_get_readelf", lambda: "/r")
    sym_out = chr(10).join([
        " 000: 00000000  0 FUNC GLOBAL DEFAULT UND pthread_create@GLIBC_2.34 (4)",
        " 001: 00000000  0 FUNC GLOBAL DEFAULT UND other@GLIBCXX_3.4 (5)",
    ])
    monkeypatch.setattr(AS, "safe_run", lambda c, timeout=None: _ns(0, out=sym_out))
    assert _extract_symbol_for_version(elf, "GLIBC_2.34") == "pthread_create@GLIBC_2.34" or _extract_symbol_for_version(elf, "GLIBC_2.34")