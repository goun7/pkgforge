"""Coverage itmesi — core/sbom.py gercel arsiv uretimi + fark alma."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import core.sbom as SB


def _fake_tools():
    return SimpleNamespace(bsdtar="bsdtar", debtap="", pacman="", makepkg="")


def _make_pkg(tmp_path: Path) -> Path:
    pkgdir = tmp_path / "stage"
    (pkgdir / "usr" / "bin").mkdir(parents=True)
    (pkgdir / "etc").mkdir(parents=True)
    info = pkgdir / ".PKGINFO"
    info.write_text(chr(10).join([
        "pkgname = demo",
        "pkgver = 2.5.0",
        "arch = x86_64",
        "desc = Test paketi",
        "depend = glibc",
    ]))
    elf = pkgdir / "usr" / "bin" / "hello"
    elf.write_bytes(bytes([0x7F]) + b"ELF" + bytes(8))
    conf = pkgdir / "etc" / "app.conf"
    conf.write_text("anahtar = deger" + chr(10))
    tar_path = tmp_path / "demo.tar"
    with open(tar_path, "wb") as fh:
        subprocess.run([
            "tar", "cf", "-", "-C", str(pkgdir),
            ".PKGINFO", "usr", "etc"], stdout=fh, check=True)
    zst = tmp_path / "demo-2.5.0-1-x86_64.pkg.tar.zst"
    subprocess.run(["zstd", "-qf", str(tar_path), "-o", str(zst)], check=True)
    return zst


def test_generate_sbom_real_archive(tmp_path):
    pkg = _make_pkg(tmp_path)
    doc = SB.generate_sbom(pkg, _fake_tools())
    assert doc.package_name == "demo"
    assert doc.package_version == "2.5.0"
    assert doc.package_arch == "x86_64"
    assert doc.package_description == "Test paketi"
    assert doc.total_files >= 4
    paths = {f.path for f in doc.files}
    assert any("hello" in p for p in paths)
    hashed = [f for f in doc.files if f.sha256]
    assert hashed, "hashli girdi beklenir"
    out = tmp_path / "sbom.json"
    SB.save_sbom(doc, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["package_name"] == "demo"


def test_generate_sbom_without_hashes(tmp_path):
    pkg = _make_pkg(tmp_path)
    doc = SB.generate_sbom(pkg, _fake_tools(), include_hashes=False)
    assert all(f.sha256 == "" for f in doc.files)


def _doc(name, ver, entries, deps):
    d = SB.SBOMDocument()
    d.package_name = name
    d.package_version = ver
    d.files = [SB.SBOMEntry(path=p, sha256=s) for p, s in entries]
    d.dependencies = list(deps)
    return d


def test_diff_sboms_reports_all_kinds():
    old = _doc("demo", "1.0", [("a", "h1"), ("b", "h2")], ["glibc"])
    new = _doc("demo", "2.0", [("a", "h9"), ("c", "h3")],
               ["glibc", "openssl"])
    diff = SB.diff_sboms(old, new)
    assert diff.added_files == ["c"]
    assert diff.removed_files == ["b"]
    assert len(diff.changed_files) == 1
    assert diff.changed_files[0]["path"] == "a"
    assert diff.added_deps == ["openssl"]
    text = diff.summary()
    assert "ayn" not in text or "De" in text
