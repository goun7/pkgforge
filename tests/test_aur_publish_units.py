"""Coverage itmesi — core/aur_publish.py hazirlama + git push akisi."""
from __future__ import annotations

from types import SimpleNamespace as NS

import core.aur_publish as AP
from core.aur_publish import (
    _extract_pkg_info,
    _generate_pkgbuild,
    _generate_srcinfo,
    detect_build_system,
    prepare_aur_package,
    push_to_aur,
)


def _ns(code, out="", err=""):
    return NS(returncode=code, stdout=out, stderr=err)

def test_extract_pkginfo_and_fallbacks(monkeypatch, tmp_path):
    pkg = tmp_path / "demo-1.2-3-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"x")
    monkeypatch.setattr(AP, "safe_run", lambda c, timeout=None: _ns(0, out="pkgname = demo" + chr(10) + "pkgver = 1.2-3"))
    info = _extract_pkg_info(pkg)
    assert info == {"name": "demo", "version": "1.2-3"}

    monkeypatch.setattr(AP, "safe_run", lambda c, timeout=None: _ns(1))
    info2 = _extract_pkg_info(pkg)
    assert info2["name"] == "demo" and info2["version"] == "1.2-3"

    weird = tmp_path / "tek-kelime.pkg.tar.zst"
    weird.write_bytes(b"x")
    monkeypatch.setattr(AP, "extract_package_name", lambda n: "ozel-ad")
    assert _extract_pkg_info(weird)["name"] == "ozel-ad"

def test_srcinfo_and_build_system(tmp_path, monkeypatch):
    pkgb = tmp_path / "PKGBUILD"
    pkgb.write_text("pkgname=demo")
    monkeypatch.setattr(AP, "safe_run", lambda c, timeout=None, **kw: _ns(0, out="pkgdesc = x"))
    assert _generate_srcinfo(pkgb) == "pkgdesc = x"
    monkeypatch.setattr(AP, "safe_run", lambda c, timeout=None, **kw: _ns(1))
    assert _generate_srcinfo(pkgb) == ""
    (tmp_path / "CMakeLists.txt").write_text("x")
    assert detect_build_system(tmp_path) == "cmake"
    empty = tmp_path / "bos"
    empty.mkdir()
    assert detect_build_system(empty) == "unknown"

def test_generate_pkgbuild_variants():
    q = chr(39)
    text_cmake = _generate_pkgbuild("demo", "1.0-2", "https://git/x", "cmake")
    assert "pkgver=1.0" in text_cmake and "pkgrel=2" in text_cmake
    assert "cmake -B build" in text_cmake
    assert ("makedepends=(" + q + "cmake" + q + ")") in text_cmake
    text_py = _generate_pkgbuild("demo", "3.1", "", "python")
    assert "python-build python-installer" in text_py
    assert chr(34) + "$url" + chr(34) in text_py
    text_go = _generate_pkgbuild("demo", "1", "u", "go")
    assert "go build -o $pkgname ." in text_go

def test_prepare_aur_package_flow(monkeypatch, tmp_path):
    pkg = tmp_path / "demo-2.0-1-x86_64.pkg.tar.zst"
    pkg.write_bytes(b"x")
    repo = tmp_path / "src"
    repo.mkdir()
    (repo / "meson.build").write_text("x")
    monkeypatch.setattr(AP, "safe_run", lambda c, timeout=None, **kw: _ns(0, out="pkgname = demo"))
    ok, _msg, aur_pkg = prepare_aur_package(pkg, tmp_path / "out", git_url="https://git/d", repo_dir=repo)
    assert ok is True and aur_pkg.name == "demo"
    pb = aur_pkg.pkgbuild.read_text()
    assert "meson setup build" in pb
    assert aur_pkg.srcinfo.exists() and aur_pkg.srcinfo.read_text() == "pkgname = demo"

def test_prepare_validation_fallback(monkeypatch, tmp_path):
    pkg = tmp_path / "demo-1-1-x.pkg.tar.zst"
    pkg.write_bytes(b"x")
    calls = {"n": 0}
    def flaky(cmd, timeout=None, **kw):
        calls["n"] += 1
        if calls["n"] <= 1:
            return _ns(1)
        return _ns(0, out="pkgname = demo")
    monkeypatch.setattr(AP, "safe_run", flaky)
    ok, _msg, _aur_pkg = prepare_aur_package(pkg, tmp_path / "out")
    assert ok is True and calls["n"] >= 2

class Recorder:
    def __init__(self, fn):
        self.fn = fn
        self.calls = []
    def __call__(self, cmd, timeout=None, cwd=None):
        self.calls.append((tuple(cmd), cwd))
        return self.fn(tuple(cmd))

def test_push_to_aur(monkeypatch, tmp_path):
    monkeypatch.setattr(AP.shutil, "which", lambda n: None)
    ok, msg = push_to_aur(tmp_path, "ssh://aur/x.git")
    assert ok is False and "git bulunamad" in msg

    monkeypatch.setattr(AP.shutil, "which", lambda n: "/usr/bin/git")
    rec = Recorder(lambda cmd: _ns(1) if cmd[1] == "init" else _ns(0))
    monkeypatch.setattr(AP, "safe_run", rec)
    d = tmp_path / "d"
    d.mkdir()
    ok2, msg2 = push_to_aur(d, "ssh://aur/x.git")
    assert ok2 is False and "git init başarısız" in msg2

    def happy(cmd):
        if cmd[1] == "remote":
            return _ns(5, out="ssh://aur/eski.git")
        return _ns(0)
    rec2 = Recorder(happy)
    monkeypatch.setattr(AP, "safe_run", rec2)
    ok3, msg3 = push_to_aur(d, "ssh://aur/yeni.git", ssh_key="/k/key")
    assert ok3 is True and "yüklendi" in msg3
    cmds = [c for c, _ in rec2.calls]
    assert any("-c" in c and "core.sshCommand" in " ".join(c) for c in cmds)
    assert not any(c[:3] == ("git", "remote", "add") for c in cmds)

    def push_fail(cmd):
        if cmd[1] == "push":
            return _ns(128, err="reddi")
        if cmd[1] == "remote":
            return _ns(1)
        return _ns(0)
    rec3 = Recorder(push_fail)
    monkeypatch.setattr(AP, "safe_run", rec3)
    ok4, msg4 = push_to_aur(d, "ssh://aur/z.git")
    assert ok4 is False and "Push başarısız" in msg4
    assert any(c[1] == "remote" and c[2] == "add" for c, _ in rec3.calls)