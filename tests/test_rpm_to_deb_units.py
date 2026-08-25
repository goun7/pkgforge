"""Coverage itmesi — core/rpm_to_deb_converter.py donusum akisi."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import core.rpm_to_deb_converter as RD


def _ns(code, out="", err=""):
    return NS(returncode=code, stdout=out, stderr=err)


def _paths(tmp_path):
    rpm = tmp_path / "hello-2.0-1.x86_64.rpm"
    rpm.write_bytes(b"RPM")
    return rpm, tmp_path / "cikti"


def test_availability(monkeypatch):
    monkeypatch.setattr(RD.shutil, "which", lambda n: "/usr/bin/" + n)
    assert RD.is_rpm_to_deb_available() is True
    monkeypatch.setattr(RD.shutil, "which", lambda n: None)
    assert RD.is_rpm_to_deb_available() is False


def test_missing_file_and_tools(monkeypatch, tmp_path):
    rpm, out = _paths(tmp_path)
    ok = RD.rpm_to_deb(tmp_path / "yok.rpm", out)
    assert ok[0] is False and "bulunamadı" in ok[1]

    rpm.write_bytes(b"x")
    monkeypatch.setattr(RD.shutil, "which", lambda n: None)
    r2 = RD.rpm_to_deb(rpm, out)
    assert r2[0] is False and "rpm2cpio bulunamadı" in r2[1]

    def partial(name):
        return "/usr/bin/rpm2cpio" if name == "rpm2cpio" else None
    monkeypatch.setattr(RD.shutil, "which", partial)
    r3 = RD.rpm_to_deb(rpm, out)
    assert r3[0] is False and "dpkg-deb bulunamadı" in r3[1]


def _happy_patch(monkeypatch, extract_rc=0, rpm_lines=None, dpkg_rc=0):
    seen = []

    def which(name):
        return "/usr/bin/" + name
    monkeypatch.setattr(RD.shutil, "which", which)

    def fake_run(cmd, timeout=None, cwd=None, **kw):
        exe = Path(cmd[0]).name
        seen.append((exe, list(cmd)))
        if exe == "bash":
            if extract_rc != 0:
                return _ns(extract_rc, err="kirik arsiv")
            Path(cwd).joinpath("usr", "bin").mkdir(parents=True,
                                                   exist_ok=True)
            Path(cwd, "usr", "bin", "hello").write_bytes(b"ELF-mock")
            return _ns(0)
        if exe == "rpm" and rpm_lines is not None:
            return _ns(0, out=chr(10).join(rpm_lines))
        if exe == "dpkg-deb":
            if dpkg_rc == 0:
                Path(cmd[-1]).write_bytes(b"DEB")
            return _ns(dpkg_rc, err="dpkg hatasi")
        return _ns(0)
    monkeypatch.setattr(RD, "safe_run", fake_run)
    return seen


def test_extract_failure(monkeypatch, tmp_path):
    rpm, out = _paths(tmp_path)
    out.mkdir()
    _happy_patch(monkeypatch, extract_rc=1)
    r = RD.rpm_to_deb(rpm, out)
    assert r[0] is False and "RPM çıkarma başarısız" in r[1]


def test_success_fallback_metadata(monkeypatch, tmp_path):
    rpm, out = _paths(tmp_path)
    out.mkdir()
    _happy_patch(monkeypatch, rpm_lines=None)
    ok, msg, deb = RD.rpm_to_deb(rpm, out)
    assert ok is True
    assert deb.name == "hello_1.0-1_amd64.deb"


def test_success_with_rpm_query_and_dpkg_fail(monkeypatch, tmp_path):
    rpm, out = _paths(tmp_path)
    out.mkdir()
    lines = ["my-app", "3.4", "2.fc40", "aarch64", "Arac",
             "https://ornek.test"]
    _happy_patch(monkeypatch, rpm_lines=lines)
    ok, msg, deb = RD.rpm_to_deb(rpm, out)
    assert ok is True
    assert deb.name == "my-app_3.4-2.fc40_arm64.deb"

    seen = _happy_patch(monkeypatch, rpm_lines=lines, dpkg_rc=1)
    ok2, msg2, d2 = RD.rpm_to_deb(rpm, out)
    assert ok2 is False and "dpkg-deb başarısız" in msg2
