"""Coverage itmesi — reproducible_build dogrulama akislari."""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import core.reproducible_build as RB


def _tools():
    return NS(makepkg="/usr/bin/makepkg", bsdtar="bsdtar")


def _ns(code, out="", err=""):
    return NS(returncode=code, stdout=out, stderr=err)


def _make_zst(tmp_path: Path, with_pkgbuild=True):
    d = tmp_path / "stage"
    d.mkdir(exist_ok=True)
    if with_pkgbuild:
        (d / "PKGBUILD").write_text("pkgname=demo")
    tar_path = tmp_path / "a.tar"
    with open(tar_path, "wb") as fh:
        subprocess.run(["tar", "cf", "-", "-C", str(d), "."],
                       stdout=fh, check=True)
    zst = tmp_path / "demo-1.0-1-x86_64.pkg.tar.zst"
    subprocess.run(["zstd", "-qf", str(tar_path), "-o", str(zst)], check=True)
    return zst


def test_missing_package_and_no_makepkg(tmp_path):
    r = RB.verify_reproducible(tmp_path / "yok.zst", _tools())
    assert r.verified is False and "bulunamadı" in r.detail
    f = tmp_path / "x.pkg.tar.zst"
    f.write_bytes(b"x")
    r2 = RB.verify_reproducible(f, NS(makepkg="", bsdtar="bsdtar"))
    assert "makepkg bulunamadı" in r2.detail


def test_extract_failure(monkeypatch, tmp_path):
    f = tmp_path / "x.pkg.tar.zst"
    f.write_bytes(b"x")
    monkeypatch.setattr(RB, "safe_run",
                        lambda cmd, timeout=None, **kw: _ns(1))
    r = RB.verify_reproducible(f, _tools())
    assert "çıkarılamadı" in r.detail


def test_no_pkgbuild_in_archive(tmp_path):
    f = _make_zst(tmp_path, with_pkgbuild=False)
    r = RB.verify_reproducible(f, _tools())
    assert "PKGBUILD bulunamadı" in r.detail


def _patch_build(monkeypatch, makepkg_rc=0, rebuild_bytes=None,
                 xdelta_write=False):
    real_run = RB.safe_run

    def fake(cmd, timeout=None, cwd=None, env=None, **kw):
        exe = Path(cmd[0]).name
        if exe == "bsdtar":
            return real_run(cmd, timeout=timeout)
        if exe == "makepkg":
            if makepkg_rc == 0 and rebuild_bytes is not None:
                dest = Path(env["PKGDEST"]) / "rebuilt.pkg.tar.zst"
                dest.write_bytes(rebuild_bytes)
            return _ns(makepkg_rc)
        if exe == "xdelta3":
            if xdelta_write:
                Path(cmd[-1]).write_bytes(b"DIFF")
            return _ns(0)
        return _ns(0)
    monkeypatch.setattr(RB, "safe_run", fake)


def test_makepkg_failure(monkeypatch, tmp_path):
    f = _make_zst(tmp_path)
    _patch_build(monkeypatch, makepkg_rc=2)
    r = RB.verify_reproducible(f, _tools())
    assert "Yeniden oluşturma başarısız" in r.detail


def test_rebuilt_output_missing(monkeypatch, tmp_path):
    f = _make_zst(tmp_path)
    _patch_build(monkeypatch, makepkg_rc=0, rebuild_bytes=None)
    r = RB.verify_reproducible(f, _tools())
    assert "çıktı paketi bulunamadı" in r.detail


def test_perfect_match(monkeypatch, tmp_path):
    f = _make_zst(tmp_path)
    _patch_build(monkeypatch, makepkg_rc=0, rebuild_bytes=f.read_bytes())
    r = RB.verify_reproducible(f, _tools())
    assert r.verified is True and r.match_ratio == 1.0
    assert r.original_hash == r.rebuild_hash


def test_mismatch_with_diff_ratio(monkeypatch, tmp_path):
    f = _make_zst(tmp_path)
    monkeypatch.setattr(RB.shutil, "which",
                        lambda n: "/usr/bin/xdelta3")
    other = f.read_bytes() + b"EK-DATA"
    _patch_build(monkeypatch, makepkg_rc=0, rebuild_bytes=other,
                 xdelta_write=True)
    r = RB.verify_reproducible(f, _tools())
    assert r.verified is False
    assert r.diff_size == 4
    assert r.match_ratio < 1.0
    assert "eşleşme oranı" in r.detail
