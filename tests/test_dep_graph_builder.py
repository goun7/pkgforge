"""Coverage itmesi — core/dep_graph.py graf kurucu yollari."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import core.dep_graph as DG


def _ns(code, out=""):
    return SimpleNamespace(returncode=code, stdout=out, stderr="")


def test_build_graph_without_pacman(monkeypatch, tmp_path):
    monkeypatch.setattr(DG.shutil, "which", lambda x: None)
    g = DG.build_dep_graph(tmp_path / "app-1.0-1-x86_64.pkg.tar.zst")
    assert any("pacman bulunamad" in w for w in g.warnings)
    assert g.nodes == {}


def _pkginfo_tar_pkg(tmp_path: Path) -> Path:
    import subprocess
    pkgdir = tmp_path / "pkg"
    pkgdir.mkdir()
    info = pkgdir / ".PKGINFO"
    info.write_text(chr(10).join([
        "pkgname = demo",
        "pkgver = 1.2.3",
        "depend = glibc",
        "depend = libfoo>=2",
    ]))
    tar_path = pkgdir / "demo.pkg.tar"
    with open(tar_path, "wb") as fh:
        subprocess.run(["tar", "cf", "-", "-C", str(pkgdir), ".PKGINFO"],
                       stdout=fh, check=True)
    zst = tmp_path / "demo-1.2.3-1-x86_64.pkg.tar.zst"
    subprocess.run(["zstd", "-qf", str(tar_path), "-o", str(zst)], check=True)
    return zst


def test_not_installed_falls_back_to_pkginfo(monkeypatch, tmp_path):
    pkg = _pkginfo_tar_pkg(tmp_path)
    monkeypatch.setattr(DG.shutil, "which", lambda x: "/usr/bin/pacman")

    def fake_run(cmd, timeout=None):
        if cmd[1] == "-Qi":
            return _ns(1)
        if cmd[1] == "xf":
            info = chr(10).join([
                "pkgname = demo",
                "pkgver = 1.2.3",
                "depend = glibc",
                "depend = libfoo>=2",
            ])
            return _ns(0, info)
        return _ns(1)
    monkeypatch.setattr(DG, "safe_run", fake_run)
    g = DG.build_dep_graph(pkg)
    assert any("kurulu de" in w for w in g.warnings)
    assert g.root == "demo"
    assert g.nodes["demo"].version == "1.2.3"
    assert g.nodes["demo"].deps == ["glibc", "libfoo"]


def test_not_installed_and_missing_file_only_warning(monkeypatch, tmp_path):
    monkeypatch.setattr(DG.shutil, "which", lambda x: "/usr/bin/pacman")
    monkeypatch.setattr(DG, "safe_run", lambda cmd, timeout=None: _ns(1))
    g = DG.build_dep_graph(tmp_path / "ghost-1-1-x86_64.pkg.tar.zst")
    assert len(g.warnings) == 1
    assert g.nodes == {} or "ghost" not in g.nodes


def test_installed_package_full_parse(monkeypatch, tmp_path):
    qi_app = chr(10).join([
        "Name            : app",
        "Version         : 1.0",
        "Depends On      : glibc libfoo>=2",
    ])
    qi_glibc = chr(10).join([
        "Name            : glibc",
        "Version         : 6.2",
        "Description     : GNU C Library",
    ])
    calls = []

    def fake_run(cmd, timeout=None):
        calls.append(list(cmd))
        if cmd[1] == "-Qi" and cmd[2] == "app":
            return _ns(0, qi_app)
        if cmd[1] == "-Qi" and cmd[2] == "glibc":
            return _ns(0, qi_glibc)
        return _ns(1)
    monkeypatch.setattr(DG.shutil, "which", lambda x: "/usr/bin/pacman")
    monkeypatch.setattr(DG, "safe_run", fake_run)
    g = DG.build_dep_graph(
        tmp_path / "app-1.0-1-x86_64.pkg.tar.zst")
    assert g.warnings == []
    assert g.root == "app"
    assert g.nodes["app"].is_installed is True
    assert g.nodes["glibc"].is_installed is True
    assert g.nodes["glibc"].version == "6.2 — GNU C Library"
    assert g.nodes["libfoo"].is_installed is False
    assert g.nodes["libfoo"].is_foreign is True
    st = g.stats()
    assert st["total"] == 3 and st["installed"] == 2 and st["foreign"] == 1


def test_is_elf_binary_magic_fallback(monkeypatch, tmp_path):
    f = tmp_path / "bin"
    f.write_bytes(bytes([0x7F]) + b"ELF" + b"x")
    monkeypatch.setattr(DG.shutil, "which", lambda x: None)
    assert DG._is_elf_binary(f) is True
    t = tmp_path / "metin.txt"
    t.write_text("selam")
    assert DG._is_elf_binary(t) is False
