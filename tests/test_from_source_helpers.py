"""Coverage itmesi — from_source yardimcilari (lisans/tanim/ikili/oserror)."""
from __future__ import annotations

import core.from_source as FS

Q = chr(34)


def test_extract_version_cmake_set_fallback(tmp_path):
    (tmp_path / "CMakeLists.txt").write_text(
        "set(PROJECT_VERSION " + Q + "9.9.9" + Q + ")")
    assert FS._extract_version_from_cmake(tmp_path) == "9.9.9"


def test_version_extractors_tolerate_unreadable(tmp_path):
    for fname in ("CMakeLists.txt", "meson.build", "Cargo.toml",
                  "pyproject.toml"):
        d = tmp_path / fname
        d.mkdir()
    assert FS._extract_version_from_cmake(tmp_path) is None
    assert FS._extract_version_from_meson(tmp_path) is None
    assert FS._extract_version_from_cargo(tmp_path) is None
    assert FS._extract_version_from_pyproject(tmp_path) is None


def test_detect_license_spdx_and_defaults(tmp_path):
    (tmp_path / "LICENSE").write_text("MIT License" + chr(10)
                                      + "Permission is hereby granted")
    assert FS._detect_license(tmp_path) == "MIT"
    empty = tmp_path / "bostan"
    empty.mkdir()
    assert FS._detect_license(empty) == "GPL-3.0-or-later"


def test_detect_license_cargo_and_pkgjson(tmp_path):
    cargo = tmp_path / "Cargo.toml"
    cargo.write_text("license = " + Q + "Apache-2.0" + Q)
    assert FS._detect_license(tmp_path) == "Apache-2.0"
    cargo.unlink()
    pj = tmp_path / "package.json"
    pj.write_text("{ " + Q + "license" + Q + ": " + Q + "ISC" + Q + " }")
    assert FS._detect_license(tmp_path) == "ISC"


def test_detect_description_prose_then_default(tmp_path):
    rm = tmp_path / "README.md"
    rm.write_text("# Baslik" + chr(10) + "Kucuk bir komut satiri araci.")
    got = FS._detect_description(tmp_path, "demo")
    assert got == "Kucuk bir komut satiri araci."
    rm.unlink()
    assert FS._detect_description(tmp_path, "demo") == \
        "demo — kaynaktan derlenen paket"


def test_detect_python_and_node(tmp_path):
    assert FS._detect_python_package(tmp_path) is False
    (tmp_path / "setup.py").write_text("")
    assert FS._detect_python_package(tmp_path) is True
    assert FS._detect_node_package(tmp_path) is False
    bad = tmp_path / "package.json"
    bad.write_text("bozuk json{{{")
    assert FS._detect_node_package(tmp_path) is False


def test_detect_binary_name_sources(tmp_path):
    cargo = tmp_path / "Cargo.toml"
    cargo.write_text("name = " + Q + "kargo-bin" + Q)
    assert FS._detect_binary_name(tmp_path, "demo") == "kargo-bin"
    cargo.rename(tmp_path / "yedek.toml")
    cm = tmp_path / "CMakeLists.txt"
    cm.write_text("add_executable(cmake_bin main.c)")
    assert FS._detect_binary_name(tmp_path, "demo") == "cmake_bin"
    cm.rename(tmp_path / "yedek.txt")
    pj = tmp_path / "package.json"
    pj.write_text("{ " + Q + "bin" + Q + ": { " + Q + "cli" + Q + ": " + Q + "x" + Q + " } }")
    assert FS._detect_binary_name(tmp_path, "demo") == "cli"
    pj.write_text("{ " + Q + "bin" + Q + ": " + Q + "tekil" + Q + " }")
    assert FS._detect_binary_name(tmp_path, "demo") == "tekil"
    pj.unlink()
    assert FS._detect_binary_name(tmp_path, "demo") == "demo"


def test_detect_binary_name_tolerates_unreadable(tmp_path):
    cm = tmp_path / "CMakeLists.txt"
    cm.mkdir()
    assert FS._detect_binary_name(tmp_path, "demo") == "demo"
