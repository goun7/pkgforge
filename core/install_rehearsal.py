"""Faz 5 (F5.14) — kurulum provasi: konteyner ici kurulum simulasyonu.

Bir paketi gercek sisteme dokunmadan tek kullanimlik bir konteynerde kurmayi
dene ve kurulacak dosya listesini (diff) dondurur. Konteyner runtime'i
(distrobox/podman/docker) yoksa ozellik zarifce devre disi kalir
(available=False + neden). Asla raise etmez.
"""
from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_REHEARSAL_TIMEOUT_S = 120
_RUNTIMES = ("distrobox", "podman", "docker")


def find_rehearsal_runtime() -> str | None:
    """Return the first available container runtime, else None."""
    for tool in _RUNTIMES:
        if shutil.which(tool):
            return tool
    return None


def _container_file_list(runtime: str, package_path: Path) -> tuple[bool, str, list[str]]:
    """Best-effort: install the package in a disposable container and list files.

    Returns (ok, message, file_list). Only podman/docker are driven directly;
    distrobox is reported as available but needs an interactive box, so it is
    surfaced as a hint instead of being executed here.
    """
    if runtime == "distrobox":
        return False, ("distrobox bulundu ancak otomatik prova icin podman/docker "
                       "onerilir; 'distrobox create' ile elle prova yapilabilir."), []
    image = "archlinux:base"
    # Guvenlik: paket adi/klasoru kullanici kaynakli oldugu icin container
    # icindeki sh -c komutuna MUTLAKA quote'lanarak gomulur (CWE-78).
    quoted_name = shlex.quote(f"/pkgdir/{package_path.name}")
    cmd = [
        runtime, "run", "--rm",
        "-v", f"{shlex.quote(str(package_path.parent))}:/pkgdir:ro",
        image,
        "sh", "-c",
        (f"pacman -U --noconfirm --needed {quoted_name} "
         f">/dev/null 2>&1 && pacman -Ql $(pacman -Qq | tail -n1) 2>/dev/null "
         f"| awk '{{print $2}}'"),
    ]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=_REHEARSAL_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Konteyner provasi calistirilamadi: {exc}", []
    if res.returncode != 0:
        return False, f"Konteyner ici kurulum basarisiz: {res.stderr[:200]}", []
    files = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
    return True, "Prova tamamlandi", files


def rehearse_install(package_path: Path | str) -> dict[str, Any]:
    """Simulate installing a package in a container; return a file-list diff.

    Returns a dict with ok/available/runtime/reason/file_count/files.
    Graceful: no container runtime -> available=False with a reason + hint.
    """
    pkg = Path(package_path)
    if not pkg.is_file():
        return {"ok": False, "available": False,
                "reason": f"Paket bulunamadi: {pkg}"}

    runtime = find_rehearsal_runtime()
    if not runtime:
        return {
            "ok": False,
            "available": False,
            "runtime": None,
            "reason": ("Konteyner runtime'i yok (distrobox/podman/docker); "
                       "prova atlandi."),
            "hint": "pacman -S distrobox  (veya podman / docker)",
        }

    ok, message, files = _container_file_list(runtime, pkg)
    return {
        "ok": ok,
        "available": True,
        "runtime": runtime,
        "reason": message,
        "file_count": len(files),
        "files": files[:500],
    }
