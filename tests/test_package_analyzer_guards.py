"""Coverage itmesi — package_analyzer hata kollari ve RPM fallback."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.package_analyzer as PA


def _ns(code, out="", err="", binary=False):
    if binary:
        return SimpleNamespace(returncode=code, stdout=out, stderr=err)
    return SimpleNamespace(returncode=code, stdout=out, stderr=err)


def _tools(**kw):
    base = {"ar": "/usr/bin/ar", "bsdtar": "bsdtar",
            "pacman": "/usr/bin/pacman", "rpm2cpio": "", "makepkg": ""}
    base.update(kw)
    return SimpleNamespace(**base)


def test_oversize_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(PA, "MAX_PIPE_INPUT_MB", 0)
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    with pytest.raises(RuntimeError) as ei:
        PA.analyze_package(f, _tools())
    assert "çok büyük" in str(ei.value)


def test_unsupported_suffix(tmp_path):
    f = tmp_path / "x.zip"
    f.write_bytes(b"x")
    with pytest.raises(ValueError) as ei:
        PA.analyze_package(f, _tools())
    assert "Desteklenmeyen" in str(ei.value)


def test_deb_without_ar(tmp_path):
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    with pytest.raises(RuntimeError) as ei:
        PA._analyze_deb(f, _tools(ar=None))
    assert chr(39) + "ar" + chr(39) in str(ei.value)


def test_deb_ar_failure(monkeypatch, tmp_path):
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    monkeypatch.setattr(PA, "safe_run",
                        lambda cmd, timeout=None, text=True, input=None: _ns(1))
    with pytest.raises(RuntimeError) as ei:
        PA._analyze_deb(f, _tools())
    assert "ar başarısız" in str(ei.value)


def test_deb_no_control_member(monkeypatch, tmp_path):
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    monkeypatch.setattr(PA, "safe_run",
                        lambda cmd, timeout=None, text=True, input=None:
                        _ns(0, out="data.tar.xz"))
    with pytest.raises(RuntimeError) as ei:
        PA._analyze_deb(f, _tools())
    assert "control.tar bulunamadı" in str(ei.value)


def test_deb_control_extract_fail_bytes_stderr(monkeypatch, tmp_path):
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    calls = {"n": 0}

    def fake_run(cmd, timeout=None, text=True, input=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _ns(0, out="control.tar.zst")
        return _ns(1, err=b"patladi", binary=True)
    monkeypatch.setattr(PA, "safe_run", fake_run)
    with pytest.raises(RuntimeError) as ei:
        PA._analyze_deb(f, _tools())
    assert "çıkarılamadı" in str(ei.value)


def test_deb_control_read_fail_both_prefixes(monkeypatch, tmp_path):
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    state = {"n": 0}

    def fake_run(cmd, timeout=None, text=True, input=None):
        state["n"] += 1
        if state["n"] == 1:
            return _ns(0, out="control.tar.zst")
        if state["n"] == 2:
            return _ns(0, out=b"pkg-content")
        return _ns(1, err=b"yok")
    monkeypatch.setattr(PA, "safe_run", fake_run)
    with pytest.raises(RuntimeError) as ei:
        PA._analyze_deb(f, _tools())
    assert "okunamadı" in str(ei.value)


def test_list_files_early_return_on_extract_fail(monkeypatch, tmp_path):
    meta = PA.PackageMetadata(file_path=tmp_path / "x.deb", package_type="deb")
    monkeypatch.setattr(PA, "safe_run",
                        lambda cmd, timeout=None, text=True, input=None: _ns(1))
    PA._extract_deb_file_list(tmp_path / "x.deb", "data.tar.zst", meta,
                              _tools())
    assert meta.file_list == []


def test_rpm_requires_rpm2cpio(tmp_path):
    with pytest.raises(RuntimeError) as ei:
        PA._analyze_rpm(tmp_path / "a.rpm", _tools(rpm2cpio=""))
    assert "rpm2cpio bulunamadı" in str(ei.value)


def test_rpm_header_bad_magic(tmp_path):
    f = tmp_path / "a.rpm"
    f.write_bytes(b"NOPE" + bytes(96))
    with pytest.raises(ValueError) as ei:
        PA._parse_rpm_header(f, PA.PackageMetadata(
            file_path=f, package_type="rpm"))
    assert "Geçersiz RPM" in str(ei.value)


def test_rpm_header_url_line_and_release(monkeypatch, tmp_path):
    import shutil as sh
    f = tmp_path / "hello-2.0-1.x86_64.rpm"
    f.write_bytes(bytes([0xED, 0xAB, 0xEE, 0xDB]) + bytes(92))
    out = chr(10).join(["hello", "2.0", "1", "x86_64", "Selam",
                        "https://hello.test"])
    monkeypatch.setattr(sh, "which",
                        lambda n: "/usr/bin/rpm" if n == "rpm" else None)
    monkeypatch.setattr(PA, "safe_run",
                        lambda cmd, timeout=None, text=True, input=None:
                        _ns(0, out=out))
    meta = PA.PackageMetadata(file_path=f, package_type="rpm")
    PA._parse_rpm_header(f, meta)
    assert meta.version == "2.0-1"
    assert meta.url == "https://hello.test"


def test_rpm_header_fallback_byte_arch_and_filename(monkeypatch, tmp_path):
    import shutil as sh
    f = tmp_path / "hello-2.0-1.rpm"
    f.write_bytes(bytes([0xED, 0xAB, 0xEE, 0xDB]) + bytes(4)
                  + (3).to_bytes(2, "big") + bytes(90))
    monkeypatch.setattr(sh, "which", lambda n: None)
    meta = PA.PackageMetadata(file_path=f, package_type="rpm")
    PA._parse_rpm_header(f, meta)
    assert meta.arch == "alpha"
    assert meta.name == "hello"
    assert meta.version == "2.0-1"


def test_check_installed_skips_invalid_name(monkeypatch, capsys):
    called = {"n": 0}

    def no_call(cmd, timeout=None, text=True, input=None):
        called["n"] += 1
        raise AssertionError("cagrilmamali")
    monkeypatch.setattr(PA, "safe_run", no_call)
    meta = PA.PackageMetadata(file_path="x", package_type="deb")
    meta.name = "--dbpath=/etc"
    PA._check_installed(meta, _tools())
    assert called["n"] == 0


def test_check_installed_flags_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(PA, "safe_run",
                        lambda cmd, timeout=None, text=True, input=None:
                        _ns(0))
    meta = PA.PackageMetadata(file_path=tmp_path / "x.deb",
                              package_type="deb")
    meta.name = "hello"
    PA._check_installed(meta, _tools())
    assert meta.already_installed is True
