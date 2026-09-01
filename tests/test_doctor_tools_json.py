"""Tur-55 A2: pkgforge doctor --tools / --json alt seçenekleri."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO / "main.py") ] + args,
        capture_output=True, text=True, check=False, env={
            **__import__("os").environ, "PKGFORGE_HOME": "/tmp/doctor_test"
        },
    )


def test_doctor_tools_returns_json() -> None:
    """doctor --tools JSON çıktı verir ve rc=0/2 döner."""
    p = _run(["doctor", "--tools"])
    assert p.returncode in (0, 2), f"unexpected rc={p.returncode}: {p.stderr}"
    # Son satır JSON bloğu içermeli
    assert '"ok"' in p.stdout
    assert '"missing_required"' in p.stdout
    assert '"missing_optional"' in p.stdout
    # JSON parse edilebilir olmalı
    json_start = p.stdout.find("{")
    parsed = json.loads(p.stdout[json_start:].split("\n\n")[0])
    assert "ok" in parsed
    assert isinstance(parsed["missing_required"], list)


def test_doctor_json_full_report() -> None:
    """doctor --json tam raporu JSON olarak verir."""
    p = _run(["doctor", "--json"])
    assert p.returncode == 0, f"rc={p.returncode}: {p.stderr}"
    parsed = json.loads(p.stdout.split("{", 1)[0] + "{" + p.stdout.split("{", 1)[1])
    # İlk satır log olabilir, JSON bloğunu bul
    start = p.stdout.find("{")
    parsed = json.loads(p.stdout[start:])
    assert "version" in parsed
    assert "tools" in parsed
    assert "keyring" in parsed
    assert "storage" in parsed
    assert "dbus" in parsed


def test_doctor_default_still_works() -> None:
    """doctor (flagsız) eski davranışı bozmamalı."""
    p = _run(["doctor"])
    assert p.returncode in (0, 1)
    assert "PkgForge Doctor" in p.stdout
    assert "Araçlar" in p.stdout
