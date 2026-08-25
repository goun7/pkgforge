"""Coverage itmesi - cli scan-image tarayici dallari + completion."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import cli


def _img(tmp_path):
    f = tmp_path / "img.tar"
    f.write_bytes(b"x")
    return f


def test_scan_trivy_image_then_fs_fallback(capsys, monkeypatch, tmp_path):
    f = _img(tmp_path)
    monkeypatch.setattr(cli.shutil, "which",
                        lambda n: "/usr/bin/trivy" if n == "trivy" else None)
    calls = []

    def fake_run(cmd, timeout=None, **kw):
        calls.append((Path(cmd[0]).name, cmd[1]))
        if cmd[1] == "image":
            return NS(returncode=2, stdout="", stderr="oci degil")
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(cli, "safe_run", fake_run)
    rc = cli._cmd_scan_image(NS(image=str(f)))
    assert rc == 0 and ("trivy", "image") in calls and ("trivy", "fs") in calls
    out = capsys.readouterr().out
    assert "Trivy: Kritik CVE bulunamadı" in out


def test_scan_trivy_findings_and_grype_clean(capsys, monkeypatch, tmp_path):
    f = _img(tmp_path)
    which_map = {"trivy": "/usr/bin/trivy", "grype": "/usr/bin/grype"}
    monkeypatch.setattr(cli.shutil, "which", lambda n: which_map.get(n))
    seen = []

    def fake_run(cmd, timeout=None, **kw):
        exe = Path(cmd[0]).name
        seen.append(exe)
        if exe == "trivy":
            return NS(returncode=1,
                      stdout="p.deb CRITICAL cvex\nother satir", stderr="")
        return NS(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(cli, "safe_run", fake_run)
    rc = cli._cmd_scan_image(NS(image=str(f)))
    out = capsys.readouterr().out
    assert rc == 1 and "Trivy bulguları" in out and "CRITICAL" in out
    assert "Grype: Yüksek-seviye açık bulunamadı" in out
    assert "görüntü güvenli" not in out


def test_scan_grype_findings_and_clamav_infected(capsys, monkeypatch, tmp_path):
    f = _img(tmp_path)
    which_map = {"grype": "/usr/bin/grype", "clamscan": "/usr/bin/clamscan"}
    monkeypatch.setattr(cli.shutil, "which", lambda n: which_map.get(n))

    def fake_run(cmd, timeout=None, **kw):
        exe = Path(cmd[0]).name
        if exe == "grype":
            assert cmd[1].startswith("file:")
            return NS(returncode=1, stdout="High sevmek", stderr="")
        return NS(returncode=1, stdout="VIRUS bulundu", stderr="")
    monkeypatch.setattr(cli, "safe_run", fake_run)
    rc = cli._cmd_scan_image(NS(image=str(f)))
    out = capsys.readouterr().out
    assert rc == 1 and "Grype bulguları" in out
    assert "ClamAV enfekte" in out and "VIRUS" in out


def test_scan_tool_errors_are_soft(capsys, monkeypatch, tmp_path):
    f = _img(tmp_path)
    which_map = {"trivy": "/t", "grype": "/g", "clamscan": "/c"}
    monkeypatch.setattr(cli.shutil, "which", lambda n: which_map.get(n))
    monkeypatch.setattr(cli, "safe_run",
                        lambda cmd, timeout=None, **kw: NS(returncode=9,
                                                           stdout="", stderr="koptu"))
    rc = cli._cmd_scan_image(NS(image=str(f)))
    out = capsys.readouterr().out
    assert rc == 1 and out.count("çalışamadı") >= 3


def test_completion_ok_and_invalid(capsys, monkeypatch):
    import core.completion as CP
    monkeypatch.setattr(CP, "generate_completion", lambda shell: "# bash script")
    rc = cli._cmd_completion(NS(shell="bash"))
    assert rc == 0 and "bash script" in capsys.readouterr().out

    def bad(shell):
        raise ValueError("bilinmeyen kabuk")
    monkeypatch.setattr(CP, "generate_completion", bad)
    rc2 = cli._cmd_completion(NS(shell="tcsh"))
    assert rc2 == 1 and "bilinmeyen kabuk" in capsys.readouterr().out