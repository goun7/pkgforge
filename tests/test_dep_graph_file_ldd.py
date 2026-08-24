"""Coverage itmesi — dep_graph build_file_dep_graph (gercek arsiv + ldd)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import core.dep_graph as DG


def _ns(code, out=""):
    return SimpleNamespace(returncode=code, stdout=out, stderr="")


def _make_pkg(tmp_path: Path, files) -> Path:
    pkgdir = tmp_path / "stage"
    for rel, data in files:
        p = pkgdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    names = [rel for rel, _ in files]
    tar_path = tmp_path / "a.tar"
    with open(tar_path, "wb") as fh:
        subprocess.run(["tar", "cf", "-", "-C", str(pkgdir)] + names,
                       stdout=fh, check=True)
    zst = tmp_path / "app-1.0-1-x86_64.pkg.tar.zst"
    subprocess.run(["zstd", "-qf", str(tar_path), "-o", str(zst)], check=True)
    return zst


LDD_OUT = chr(10).join([
    chr(9) + "linux-vdso.so.1 (0x00007ffd)",
    chr(9) + "libcrypto.so.3 => /usr/lib/libcrypto.so.3 (0x00007f)",
    chr(9) + "libmissing.so.1 => not found",
])


def _which_no_file(monkeypatch):
    def which(name):
        return None if name == "file" else "/usr/bin/" + name
    monkeypatch.setattr(DG.shutil, "which", which)


def _patch_ldd(monkeypatch):
    real_run = DG.safe_run

    def fake_run(cmd, timeout=None):
        if Path(cmd[0]).name == "ldd":
            return _ns(0, LDD_OUT)
        return real_run(cmd, timeout=timeout)
    monkeypatch.setattr(DG, "safe_run", fake_run)


def test_file_graph_full_flow(monkeypatch, tmp_path):
    pkg = _make_pkg(tmp_path, [
        ("usr/bin/appbin", bytes([0x7F]) + b"ELF" + bytes(20)),
        ("etc/app.conf", b"k=v"),
        ("README.md", b"okuma"),
    ])
    _which_no_file(monkeypatch)
    _patch_ldd(monkeypatch)
    g = DG.build_file_dep_graph(pkg)
    assert g.root == "app"
    assert "usr/bin/appbin" in g.nodes
    assert g.nodes["libcrypto.so.3"].is_installed is True
    assert g.nodes["libmissing.so.1"].is_installed is False
    names = [n.name for n in g.nodes.values()]
    assert "ld-linux-x86-64.so.2" not in names
    assert "linux-vdso.so.1" not in names
    assert g.warnings == []


def test_file_graph_without_ldd_warns(monkeypatch, tmp_path):
    pkg = _make_pkg(tmp_path, [("usr/bin/x", bytes([0x7F]) + b"ELF")])
    monkeypatch.setattr(DG.shutil, "which", lambda name: None)
    g = DG.build_file_dep_graph(pkg)
    assert any("ldd bulunamad" in w for w in g.warnings)


def test_file_graph_missing_file(monkeypatch, tmp_path):
    g = DG.build_file_dep_graph(tmp_path / "ghost-1-1-x86_64.pkg.tar.zst")
    assert any("bulunamad" in w for w in g.warnings)


def test_file_graph_bad_archive(monkeypatch, tmp_path):
    bad = tmp_path / "junk-1-1-x86_64.pkg.tar.zst"
    bad.write_bytes(b"bu bir arsiv degil")
    monkeypatch.setattr(DG.shutil, "which", lambda name: "/usr/bin/" + name)
    g = DG.build_file_dep_graph(bad)
    assert len(g.warnings) == 1


def test_file_graph_no_elf_found(monkeypatch, tmp_path):
    pkg = _make_pkg(tmp_path, [("etc/sadece.conf", b"x"), ("NOT.md", b"y")])
    _which_no_file(monkeypatch)
    _patch_ldd(monkeypatch)
    g = DG.build_file_dep_graph(pkg)
    assert any("ELF dosyas" in w for w in g.warnings)
