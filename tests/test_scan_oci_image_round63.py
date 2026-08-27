"""Tur-63 — core.malware_scanner.scan_oci_image birim testleri."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import core.malware_scanner as MS

NL = chr(10)


def _img(tmp_path: Path) -> Path:
    f = tmp_path / "img.tar"
    f.write_bytes(b"x")
    return f


def test_no_scanner_available(monkeypatch, tmp_path):
    monkeypatch.setattr(MS.shutil, "which", lambda n: None)
    res = MS.scan_oci_image(_img(tmp_path))
    assert res["clean"] is True
    assert res["tools"] == {"trivy": False, "grype": False, "clamscan": False}
    assert "bulunamadi" in res["detail"]


def test_trivy_clean_image(monkeypatch, tmp_path):
    monkeypatch.setattr(MS.shutil, "which",
                        lambda n: "/usr/bin/trivy" if n == "trivy" else None)
    monkeypatch.setattr(MS, "safe_run",
                        lambda cmd, timeout=None, **k: NS(returncode=0, stdout="", stderr=""))
    res = MS.scan_oci_image(_img(tmp_path))
    assert res["clean"] is True and res["findings"] == []
    assert res["tools"]["trivy"] is True


def test_trivy_image_fails_fs_fallback_clean(monkeypatch, tmp_path):
    monkeypatch.setattr(MS.shutil, "which",
                        lambda n: "/usr/bin/trivy" if n == "trivy" else None)
    calls = []

    def fake_run(cmd, timeout=None, **k):
        calls.append(cmd[1])
        if cmd[1] == "image":
            return NS(returncode=2, stdout="", stderr="oci degil")
        return NS(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(MS, "safe_run", fake_run)
    res = MS.scan_oci_image(_img(tmp_path))
    assert res["clean"] is True
    assert "image" in calls and "fs" in calls


def test_trivy_findings(monkeypatch, tmp_path):
    monkeypatch.setattr(MS.shutil, "which",
                        lambda n: "/usr/bin/trivy" if n == "trivy" else None)
    out = NL.join(["pkg CRITICAL cve-1", "ok satir", "HIGH issue"])
    monkeypatch.setattr(MS, "safe_run", lambda cmd, timeout=None, **k: NS(
        returncode=1, stdout=out, stderr=""))
    res = MS.scan_oci_image(_img(tmp_path))
    assert res["clean"] is False
    assert len(res["findings"]) == 2
    assert res["findings"][0]["tool"] == "trivy"
    assert "bulgu" in res["detail"]


def test_grype_clean(monkeypatch, tmp_path):
    monkeypatch.setattr(MS.shutil, "which",
                        lambda n: "/usr/bin/grype" if n == "grype" else None)
    monkeypatch.setattr(MS, "safe_run",
                        lambda cmd, timeout=None, **k: NS(returncode=0, stdout="", stderr=""))
    res = MS.scan_oci_image(_img(tmp_path))
    assert res["clean"] is True and res["tools"]["grype"] is True


def test_grype_findings_dir_target(monkeypatch, tmp_path):
    d = tmp_path / "rootfs"
    d.mkdir()
    monkeypatch.setattr(MS.shutil, "which",
                        lambda n: "/usr/bin/grype" if n == "grype" else None)
    seen = []

    def fake_run(cmd, timeout=None, **k):
        seen.append(cmd[1])
        return NS(returncode=1, stdout=NL.join(["lib High vuln", "low satir"]), stderr="")

    monkeypatch.setattr(MS, "safe_run", fake_run)
    res = MS.scan_oci_image(d)
    assert res["clean"] is False
    assert seen[0].startswith("dir:")
    assert res["findings"][0]["tool"] == "grype"


def test_clamscan_clean(monkeypatch, tmp_path):
    monkeypatch.setattr(MS.shutil, "which",
                        lambda n: "/usr/bin/clamscan" if n == "clamscan" else None)
    monkeypatch.setattr(MS, "safe_run",
                        lambda cmd, timeout=None, **k: NS(returncode=0, stdout="", stderr=""))
    res = MS.scan_oci_image(_img(tmp_path))
    assert res["clean"] is True and res["tools"]["clamscan"] is True


def test_clamscan_infected(monkeypatch, tmp_path):
    monkeypatch.setattr(MS.shutil, "which",
                        lambda n: "/usr/bin/clamscan" if n == "clamscan" else None)
    monkeypatch.setattr(MS, "safe_run", lambda cmd, timeout=None, **k: NS(
        returncode=1, stdout="/x/eicar FOUND", stderr=""))
    res = MS.scan_oci_image(_img(tmp_path))
    assert res["clean"] is False
    assert res["findings"][0]["severity"] == "MALWARE"


def test_mixed_trivy_clean_grype_findings(monkeypatch, tmp_path):
    which_map = {"trivy": "/usr/bin/trivy", "grype": "/usr/bin/grype"}
    monkeypatch.setattr(MS.shutil, "which", lambda n: which_map.get(n))

    def fake_run(cmd, timeout=None, **k):
        exe = Path(cmd[0]).name
        if exe == "trivy":
            return NS(returncode=0, stdout="", stderr="")
        return NS(returncode=1, stdout="pkg Critical cve", stderr="")

    monkeypatch.setattr(MS, "safe_run", fake_run)
    res = MS.scan_oci_image(_img(tmp_path))
    assert res["clean"] is False
    assert res["findings"][0]["tool"] == "grype"
