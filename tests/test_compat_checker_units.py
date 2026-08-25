"""Coverage itmesi - core/compatibility_checker.py bagimlilik/yardimcilar."""
from __future__ import annotations

from types import SimpleNamespace as NS

import core.compatibility_checker as CC
from config import ToolPaths
from core.compatibility_checker import (
    CheckSeverity,
    _check_dependencies,
    _elf_max_glibc,
    _get_system_glibc,
    _system_lib_sonames,
)


def _tools():
    return ToolPaths(pkexec="/usr/bin/pkexec", pacman="/usr/bin/pacman",
                     readelf="/usr/bin/readelf", ldd="/usr/bin/ldd")


def test_deps_empty_passes():
    res = _check_dependencies([], _tools())
    assert len(res) == 1 and res[0].severity == CheckSeverity.PASS


def test_deps_resolved_installed_and_repo(monkeypatch):
    calls = []

    def fake_run(cmd, timeout=None, **kw):
        calls.append(cmd[1])
        if cmd[1] == "-Qi":
            return NS(returncode=0, stdout="kurulu", stderr="")
        return NS(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(CC, "safe_run", fake_run)
    res = _check_dependencies(["gtk3", "libx11>=1.8"], _tools())
    assert res[0].severity == CheckSeverity.PASS
    assert "Tüm bağımlılıklar (2)" in res[0].message


def test_deps_dynamic_file_lookup_and_missing(monkeypatch):
    def fake_run(cmd, timeout=None, **kw):
        if cmd[1] == "-Fq":
            return NS(returncode=0, stdout="usr/lib/libfoo.so\nextra/libbar", stderr="")
        return NS(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(CC, "safe_run", fake_run)
    res = _check_dependencies(["libfoo"], _tools())
    assert res[0].severity == CheckSeverity.PASS
    assert any("→" in d for d in res[0].details)

    def always_miss(cmd, timeout=None, **kw):
        return NS(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(CC, "safe_run", always_miss)
    res2 = _check_dependencies(["yok-paket"], _tools())
    assert res2[0].severity == CheckSeverity.WARNING
    assert "1/1 bağımlılık çözümlenemedi" in res2[0].message

    res3 = _check_dependencies(["!!!kotu;ad"], _tools())
    assert any("geçersiz ad" in d for d in res3[0].details)


def test_system_lib_sonames(monkeypatch):
    import shutil as _shutil
    monkeypatch.setattr(_shutil, "which", lambda n: None)
    assert _system_lib_sonames() == set()

    monkeypatch.setattr(_shutil, "which", lambda n: "/usr/bin/ldconfig")
    monkeypatch.setattr(CC, "safe_run", lambda c, timeout=None: NS(
        returncode=0, stdout="libc.so.6 => /usr/lib/libc.so.6\nlibm.so => x", stderr=""))
    s = _system_lib_sonames()
    assert "libc.so.6" in s and "libm.so" in s

    def boom(cmd, timeout=None, **kw):
        raise OSError("bus koptu")
    monkeypatch.setattr(CC, "safe_run", boom)
    assert _system_lib_sonames() == set()


def test_elf_max_glibc(monkeypatch):
    tools = ToolPaths(pkexec="", pacman="", readelf=None, ldd=None)
    assert _elf_max_glibc("/tmp/x", tools) == ""

    tools2 = ToolPaths(pkexec="", pacman="", readelf="/usr/bin/readelf", ldd=None)
    monkeypatch.setattr(CC, "safe_run", lambda c, timeout=None: NS(
        returncode=0, stdout="GLIBC_2.34(GLIBC_2.2.5)\nGLIBC_2.17", stderr=""))
    best = _elf_max_glibc("/tmp/x", tools2)
    assert best in ("2.34", "2.34.0") or float(best) >= 2.34

    monkeypatch.setattr(CC, "safe_run", lambda c, timeout=None: NS(
        returncode=0, stdout="glibc yok", stderr=""))
    assert _elf_max_glibc("/tmp/y", tools2) == ""


def test_get_system_glibc(monkeypatch):
    tools = ToolPaths(pkexec="", pacman="", readelf=None, ldd=None)
    assert _get_system_glibc(tools) == ""

    tools2 = ToolPaths(pkexec="", pacman="", readelf=None, ldd="/usr/bin/ldd")
    monkeypatch.setattr(CC, "safe_run", lambda c, timeout=None: NS(
        returncode=0, stdout="ldd (GNU libc) 2.39", stderr=""))
    assert _get_system_glibc(tools2) == "2.39"