"""core.maps: Debian ad eslestirme + lisans + derleme sonlandirma testleri."""
from __future__ import annotations

from pathlib import Path

from core.dep_resolver import collect_script_interpreters
from core.maps import (
    arch_license,
    debian_dep_to_arch,
    finalize_build_output,
    write_license_stub,
)


def test_debian_dep_known():
    assert debian_dep_to_arch("libc6") == "glibc"
    assert debian_dep_to_arch("LIBSTDC++6") == "gcc-libs"
    assert debian_dep_to_arch("bash") == "bash"


def test_debian_dep_constraints_and_multiarch():
    assert debian_dep_to_arch("libc6 (>= 2.34)") == "glibc"
    assert debian_dep_to_arch("libc6:amd64") == "glibc"
    assert debian_dep_to_arch("libssl3 (= 3.0.9-1)") == "openssl"


def test_debian_dep_unknown_and_empty():
    assert debian_dep_to_arch("bilinmeyen-paket-xyz") is None
    assert debian_dep_to_arch("") is None
    assert debian_dep_to_arch("(>= 1.0)") is None


def test_arch_license_spdx_hits():
    assert arch_license("GPL-3", "foo") == "GPL-3.0-only"
    assert arch_license("MIT License", "foo") == "MIT"
    assert arch_license("Apache License, Version 2.0", "foo") == "Apache-2.0"
    assert arch_license("BSD 3-Clause", "foo") == "BSD-3-Clause"


def test_arch_license_fallback_is_licenseref():
    assert arch_license("", "hello") == "LicenseRef-hello-unknown"
    assert arch_license("proprietary eula", "firmware") == "LicenseRef-firmware-unknown"
    # bare 'custom' must never leak through (namcap E since 3.6)
    assert arch_license("custom", "x") == "LicenseRef-x-unknown"
    # pkgname sanitized for the LicenseRef token
    assert arch_license("", "Kotu Ad!") == "LicenseRef-Kotu-Ad--unknown"


def test_write_license_stub(tmp_path: Path):
    stub = write_license_stub(tmp_path, "hello")
    assert stub is not None and stub.is_file()
    assert stub.parent.name == "hello"
    text = stub.read_text(encoding="utf-8")
    assert "hello" in text and "UNKNOWN" in text


def test_write_license_stub_failure_returns_none(tmp_path: Path):
    blocker = tmp_path / "dosya"
    blocker.write_bytes(b"x")
    # src_root bir dosya → mkdir basarisiz → None (donusum surer)
    assert write_license_stub(blocker, "hello") is None


def test_finalize_moves_and_cleans(tmp_path: Path):
    build = tmp_path / "native_build"
    (build / "src").mkdir(parents=True)
    (build / "pkg").mkdir(parents=True)
    (build / "src" / "iz.tmp").write_bytes(b"s")
    (build / "PKGBUILD").write_text("pkgname='a'\n", encoding="utf-8")
    out_dir = build / "pkgout"
    out_dir.mkdir(parents=True)
    artifact = out_dir / "a-1.0-1-x86_64.pkg.tar.zst"
    artifact.write_bytes(b"P")

    final = finalize_build_output(build, tmp_path)
    assert final == tmp_path / "a-1.0-1-x86_64.pkg.tar.zst"
    assert final is not None and final.is_file()
    assert (build / "PKGBUILD").is_file()       # inceleme icin saklanir
    assert not (build / "src").exists()
    assert not (build / "pkg").exists()
    assert not artifact.exists()


def test_finalize_no_artifact_returns_none(tmp_path: Path):
    build = tmp_path / "build"
    build.mkdir()
    assert finalize_build_output(build, tmp_path) is None


def test_finalize_overwrites_same_name(tmp_path: Path):
    build = tmp_path / "native_build"
    out_dir = build / "pkgout"
    out_dir.mkdir(parents=True)
    (out_dir / "a-1.0-1-x86_64.pkg.tar.zst").write_bytes(b"YENI")
    eski = tmp_path / "a-1.0-1-x86_64.pkg.tar.zst"
    eski.write_bytes(b"ESKI")

    final = finalize_build_output(build, tmp_path)
    assert final == eski and final.read_bytes() == b"YENI"


def test_finalize_output_unwritable_returns_none(tmp_path: Path):
    build = tmp_path / "build"
    out_dir = build / "pkgout"
    out_dir.mkdir(parents=True)
    (out_dir / "a-1.0-1-x86_64.pkg.tar.zst").write_bytes(b"P")
    # cikti dizini bir dosya: mkdir basarisiz → None (donusum surer)
    engel = tmp_path / "engel"
    engel.write_bytes(b"x")
    assert finalize_build_output(build, engel) is None


def test_finalize_already_at_root(tmp_path: Path):
    build = tmp_path / "build"
    build.mkdir()
    artifact = build / "b-1.0-1-any.pkg.tar.zst"
    artifact.write_bytes(b"P")
    # ayni dizin hem build hem cikti: tasima yok, yol aynen doner
    final = finalize_build_output(build, build)
    assert final == artifact and artifact.is_file()


def _fake_tools():
    from config import discover_tools

    return discover_tools()


def test_collect_script_interpreters(tmp_path: Path):
    (tmp_path / "kos.sh").write_bytes(b"#!/bin/sh\necho hi\n")
    (tmp_path / "uyg.py").write_bytes(b"#!/usr/bin/env python3\nprint(1)\n")
    (tmp_path / "dogrudan.pl").write_bytes(b"#!/usr/bin/perl\nprint 1;\n")
    (tmp_path / "bilinmeyen.xyz").write_bytes(b"#!/opt/tuhaf/calis\n")
    (tmp_path / "duzmetin.txt").write_bytes(b"shebang yok\n")
    (tmp_path / "ikon.png").write_bytes(bytes([0x89, 0x50, 0x4E, 0x47]) + b"#!sahte\n")

    found = collect_script_interpreters(tmp_path, _fake_tools())
    assert found == {"bash", "python", "perl"}


def test_collect_script_interpreters_empty(tmp_path: Path):
    assert collect_script_interpreters(tmp_path, _fake_tools()) == set()
