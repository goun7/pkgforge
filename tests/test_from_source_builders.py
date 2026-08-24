"""Coverage itmesi — core/from_source.py PKGBUILD uretici dallari."""
from __future__ import annotations

from pathlib import Path

from core.from_source import generate_pkgbuild_from_source

Q = chr(34)


def _kv(key: str, value: str) -> str:
    return key + " = " + Q + value + Q


def _repo(tmp_path: Path, files) -> Path:
    for fname, text in files:
        p = tmp_path / fname
        p.write_text(text, encoding="utf-8")
    return tmp_path


def test_pkgbuild_cmake(tmp_path):
    repo = _repo(tmp_path, [("CMakeLists.txt",
        "project(demo VERSION 1.2.3 LANGUAGES C)")])
    out = generate_pkgbuild_from_source(
        "demo", "https://x/demo.git", "cmake", repo)
    assert "pkgver=1.2.3" in out
    assert "cmake -B build" in out


def test_pkgbuild_meson(tmp_path):
    mb = ("project(" + Q + "demo" + Q + ", version: "
          + Q + "2.0.0" + Q + ")")
    repo = _repo(tmp_path, [("meson.build", mb)])
    out = generate_pkgbuild_from_source(
        "demo", "https://x/demo.git", "meson", repo)
    assert "meson setup build" in out
    assert "meson install" in out


def test_pkgbuild_cargo(tmp_path):
    toml = chr(10).join([
        "[package]",
        _kv("name", "demo"),
        _kv("version", "0.5.0"),
    ])
    repo = _repo(tmp_path, [("Cargo.toml", toml)])
    out = generate_pkgbuild_from_source(
        "demo", "https://x/demo.git", "cargo", repo)
    assert "pkgver=0.5.0" in out
    assert "cargo build --release" in out
    assert "rust" in out


def test_pkgbuild_autotools_fallback_version(tmp_path):
    out = generate_pkgbuild_from_source(
        "demo", "https://x/demo.git", "autotools", tmp_path)
    assert "pkgver=0.0.1" in out
    assert "./configure --prefix=/usr" in out


def test_pkgbuild_python(tmp_path):
    toml = chr(10).join(["[project]", _kv("name", "demo"),
                         _kv("version", "3.1.4")])
    repo = _repo(tmp_path, [("pyproject.toml", toml)])
    out = generate_pkgbuild_from_source(
        "demo", "https://x/demo.git", "python", repo)
    assert "pkgver=3.1.4" in out
    assert "python -m build" in out


def test_pkgbuild_node_branch_via_package_json(tmp_path):
    pj = ("{ " + Q + "name" + Q + ": " + Q + "demo" + Q
          + ", " + Q + "scripts" + Q + ": {} }")
    repo = _repo(tmp_path, [("package.json", pj)])
    out = generate_pkgbuild_from_source(
        "demo", "https://x/demo.git", "make", repo)
    assert "npm ci" in out


def test_pkgbuild_generic_gcc_fallback(tmp_path):
    out = generate_pkgbuild_from_source(
        "demo", "https://x/demo.git", "yok", tmp_path)
    assert "pkgname=demo" in out
    assert "https://x/demo.git" in out
