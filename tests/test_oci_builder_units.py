"""Coverage itmesi — core/oci_builder.py buildah/podman akislari."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import core.oci_builder as OB


def _ns(code):
    return NS(returncode=code, stdout="", stderr="hata")


def test_runtime_availability(monkeypatch):
    monkeypatch.setattr(OB.shutil, "which", lambda n: None)
    assert OB.is_container_runtime_available() is False


def test_build_missing_pkg(monkeypatch, tmp_path):
    ok, msg, out = OB.build_oci_image(tmp_path / "yok.zst", None)
    assert ok is False and out is None and "bulunamadı" in msg


def test_build_without_runtime(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x86_64.pkg.tar.zst"
    f.write_bytes(b"x")
    monkeypatch.setattr(OB.shutil, "which", lambda n: None)
    ok, msg, _out = OB.build_oci_image(f, None)
    assert ok is False and "buildah" in msg and "podman" in msg


def _patch(monkeypatch, runtime, fail_op=None):
    seen = []

    def fake_run(cmd, timeout=None, **kw):
        exe = Path(cmd[0]).name
        op = cmd[1] if len(cmd) > 1 else ""
        rc = 1 if (runtime == exe and fail_op == op) else 0
        seen.append((exe, op))
        return NS(returncode=rc, stdout="", stderr="hata")
    monkeypatch.setattr(OB, "safe_run", fake_run)
    return seen


def test_buildah_happy_path(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x86_64.pkg.tar.zst"
    f.write_bytes(b"x")
    out_file = tmp_path / "cikti.oci.tar"
    monkeypatch.setattr(OB.shutil, "which",
                        lambda n: "/usr/bin/buildah" if n == "buildah" else None)
    seen = _patch(monkeypatch, "buildah")
    ok, _msg, out = OB.build_oci_image(f, None, tag="pkgforge/demo:v1",
                                      output_file=out_file)
    assert ok is True and out == out_file
    assert ("buildah", "commit") in seen and ("buildah", "push") in seen
    assert ("buildah", "rmi") in seen


def test_buildah_stage_failures_cleanup(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x86_64.pkg.tar.zst"
    f.write_bytes(b"x")
    monkeypatch.setattr(OB.shutil, "which",
                        lambda n: "/usr/bin/buildah" if n == "buildah" else None)
    for bad_op in ("from", "copy", "commit", "push"):
        seen = _patch(monkeypatch, "buildah", fail_op=bad_op)
        ok, msg, _out = OB.build_oci_image(f, None)
        assert ok is False and bad_op in msg, bad_op
        if bad_op != "from":
            assert ("buildah", "rm") in seen, bad_op


def test_podman_success_and_failures(monkeypatch, tmp_path):
    f = tmp_path / "demo-1-1-x86_64.pkg.tar.zst"
    f.write_bytes(b"x")
    out_file = tmp_path / "p.oci.tar"
    monkeypatch.setattr(OB.shutil, "which",
                        lambda n: "/usr/bin/podman" if n == "podman" else None)
    seen = _patch(monkeypatch, "podman")
    ok, _msg, out = OB.build_oci_image(f, None, output_file=out_file)
    assert ok is True and out == out_file
    assert ("podman", "save") in seen

    for bad_op in ("build", "save"):
        _patch(monkeypatch, "podman", fail_op=bad_op)
        ok2, msg2, _out2 = OB.build_oci_image(f, None)
        assert ok2 is False and bad_op in msg2, bad_op
