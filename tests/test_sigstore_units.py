"""Coverage itmesi — core/sigstore.py imza/dogrulama akislari."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import core.sigstore as SG


def _ns(code, out="", err=""):
    return NS(returncode=code, stdout=out, stderr=err)


def test_summary_branches(tmp_path):
    okr = SG.SigstoreResult(success=True, message="tam",
                            log_index="123", bundle_path=tmp_path)
    s = okr.summary()
    assert "✅" in s and "Rekor" in s and "Bundle" in s
    badr = SG.SigstoreResult(success=False, message="koptu")
    assert "❌" in badr.summary()


def test_sign_without_cosign(monkeypatch, tmp_path):
    monkeypatch.setattr(SG.shutil, "which", lambda n: None)
    r = SG.sign_with_sigstore(tmp_path / "x.deb")
    assert r.success is False and "cosign bulunamadı" in r.message


def test_sign_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(SG.shutil, "which", lambda n: "/usr/bin/cosign")
    r = SG.sign_with_sigstore(tmp_path / "yok.deb")
    assert r.success is False and "Dosya bulunamadı" in r.message


def _sign_cmd_capture(monkeypatch, rc=0, stdout=""):
    seen = {}

    def fake_run(cmd, timeout=None, **kw):
        seen["cmd"] = list(cmd)
        if rc == 0 and "--output-signature" in cmd:
            Path(cmd[cmd.index("--output-signature") + 1]).write_text("imza")
        return _ns(rc, out=stdout)
    monkeypatch.setattr(SG, "safe_run", fake_run)
    return seen


def test_sign_key_based_success(monkeypatch, tmp_path):
    f = tmp_path / "paket.pkg.tar.zst"
    f.write_bytes(b"x")
    monkeypatch.setattr(SG.shutil, "which", lambda n: "/usr/bin/cosign")
    seen = _sign_cmd_capture(monkeypatch, 0)
    r = SG.sign_with_sigstore(f, key_path="/keys/gizli.key")
    assert r.success is True and r.signature_path.is_file()
    assert "--key" in seen["cmd"] and "/keys/gizli.key" in seen["cmd"]


def test_sign_keyless_with_rekor_index(monkeypatch, tmp_path):
    f = tmp_path / "paket.pkg.tar.zst"
    f.write_bytes(b"x")
    monkeypatch.setattr(SG.shutil, "which", lambda n: "/usr/bin/cosign")
    out_line = "tlog entry created: rekor 42"
    seen = _sign_cmd_capture(monkeypatch, 0, stdout=out_line)
    r = SG.sign_with_sigstore(f, oidc_issuer="https://o",
                              certificate_identity="a@b.c")
    assert r.success is True and r.log_index == out_line.strip()
    c = seen["cmd"]
    assert "--yes" in c and "https://o" in c and "a@b.c" in c


def test_sign_failure_bytes_stderr(monkeypatch, tmp_path):
    f = tmp_path / "p.pkg.tar.zst"
    f.write_bytes(b"x")
    monkeypatch.setattr(SG.shutil, "which", lambda n: "/usr/bin/cosign")
    monkeypatch.setattr(SG, "safe_run",
                        lambda cmd, timeout=None, **kw:
                        _ns(1, err=b"red-edildi"))
    r = SG.sign_with_sigstore(f)
    assert r.success is False and "İmzalama başarısız" in r.message


def test_verify_guards_and_success(monkeypatch, tmp_path):
    monkeypatch.setattr(SG.shutil, "which", lambda n: None)
    r0 = SG.verify_with_sigstore(tmp_path / "x.deb")
    assert r0.success is False

    monkeypatch.setattr(SG.shutil, "which", lambda n: "/usr/bin/cosign")
    r1 = SG.verify_with_sigstore(tmp_path / "yok.deb")
    assert r1.success is False and "Dosya bulunamadı" in r1.message

    f = tmp_path / "p.pkg.tar.zst"
    f.write_bytes(b"x")
    (tmp_path / "p.pkg.tar.zst.sig").write_text("imza")
    seen = {}

    def fake_run(cmd, timeout=None, **kw):
        seen["cmd"] = list(cmd)
        return _ns(0)
    monkeypatch.setattr(SG, "safe_run", fake_run)
    r2 = SG.verify_with_sigstore(f, key_path="/keys/acik.key")
    assert r2.success is True
    assert "--signature" in seen["cmd"]
    assert "--certificate-identity-regexp=.*" not in seen["cmd"]


def test_verify_keyless_defaults_and_failure(monkeypatch, tmp_path):
    f = tmp_path / "p.pkg.tar.zst"
    f.write_bytes(b"x")
    seen = {}

    def fake_run(cmd, timeout=None, **kw):
        seen["cmd"] = list(cmd)
        return _ns(1, err=b"gecersiz")
    monkeypatch.setattr(SG, "safe_run", fake_run)
    monkeypatch.setattr(SG.shutil, "which", lambda n: "/usr/bin/cosign")
    r = SG.verify_with_sigstore(f)
    assert r.success is False and "Doğrulama başarısız" in r.message
    c = seen["cmd"]
    assert "--certificate-identity-regexp=.*" in c
    assert "--certificate-oidc-issuer-regexp=.*" in c
