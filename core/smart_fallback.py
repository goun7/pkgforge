"""PkgForge — Smart Fallback Chain.

Automatically tries multiple conversion methods in order of preference,
logging which method succeeded. This eliminates manual fallback logic
from the pipeline.

Fallback order:
1. Native converter (fastest, no external deps)
2. debtap (community tool, well-tested)
3. Docker/podman (isolated build, most compatible)
4. distrobox (container fallback, last resort)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import ToolPaths

log = logging.getLogger(__name__)


@dataclass
class FallbackResult:
    """Result of a fallback chain attempt."""

    success: bool
    method: str          # Which method succeeded
    message: str
    output_pkg: Path | None = None
    attempts: list[dict[str, Any]] = None  # History of all attempts

    def __post_init__(self):
        if self.attempts is None:
            self.attempts = []


def _try_native_deb(deb_path: Path, output_dir: Path, tools: ToolPaths) -> tuple[bool, str, Path | None]:
    """Try native DEB converter."""
    if not tools.makepkg or not tools.bsdtar:
        return False, "makepkg veya bsdtar bulunamadı", None

    try:
        from core.subprocess_converters import NativeDebConverterSubprocess
        converter = NativeDebConverterSubprocess(tools)
        result: dict[str, Any] = {}
        import threading
        done = threading.Event()

        def on_done(success: bool, msg: str, pkg: Any) -> None:
            result.update(success=success, message=msg, output_pkg=pkg)
            done.set()

        converter.finished.connect(on_done)
        converter.convert(deb_path, output_dir)
        done.wait(timeout=120)

        return result.get("success", False), result.get("message", ""), result.get("output_pkg")
    except Exception as exc:
        return False, f"Native dönüşüm hatası: {exc}", None


def _try_debtap(deb_path: Path, output_dir: Path, tools: ToolPaths) -> tuple[bool, str, Path | None]:
    """Try debtap converter."""
    if not tools.debtap:
        return False, "debtap bulunamadı", None

    try:
        from core.deb_converter import DebConverter
        converter = DebConverter(tools)
        result: dict[str, Any] = {}
        import threading
        done = threading.Event()

        def on_done(success: bool, msg: str, pkg: Any) -> None:
            result.update(success=success, message=msg, output_pkg=pkg)
            done.set()

        converter.finished.connect(on_done)
        converter.convert(deb_path, output_dir)
        done.wait(timeout=180)

        return result.get("success", False), result.get("message", ""), result.get("output_pkg")
    except Exception as exc:
        return False, f"debtap hatası: {exc}", None


def _try_docker(deb_path: Path, output_dir: Path, tools: ToolPaths) -> tuple[bool, str, Path | None]:
    """Try building in a Docker container."""
    docker = shutil.which("docker") or shutil.which("podman")
    if not docker:
        return False, "docker/podman bulunamadı", None

    try:
        # Create a minimal Dockerfile for building
        dockerfile_content = f"""FROM archlinux:latest
RUN pacman -Syu --noconfirm && pacman -S --noconfirm base-devel docker sudo
COPY {deb_path.name} /tmp/
RUN mkdir -p /build && cp /tmp/{deb_path.name} /build/
WORKDIR /build
"""
        import tempfile
        with tempfile.TemporaryDirectory(prefix="pkgforge_docker_") as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "Dockerfile").write_text(dockerfile_content)
            shutil.copy2(deb_path, tmp / deb_path.name)

            # Build container
            res = subprocess.run(
                [docker, "build", "-t", "pkgforge-build", str(tmp)],
                capture_output=True, text=True, timeout=300,
            )
            if res.returncode != 0:
                return False, f"Docker build başarısız: {res.stderr[:200]}", None

            # Run conversion inside container
            res = subprocess.run(
                [docker, "run", "--rm", "pkgforge-build",
                 "bash", "-c", "pacman -S --noconfirm debtap && debtap -u && debtap /tmp/*.deb"],
                capture_output=True, text=True, timeout=300,
            )
            if res.returncode != 0:
                return False, f"Docker dönüşüm başarısız: {res.stderr[:200]}", None

            # Extract output
            # TODO: Copy .pkg.tar.zst from container
            return False, "Docker çıkarma henüz implemente edilmedi", None

    except Exception as exc:
        return False, f"Docker hatası: {exc}", None


def _try_distrobox(deb_path: Path, output_dir: Path, tools: ToolPaths) -> tuple[bool, str, Path | None]:
    """Try building in distrobox."""
    distrobox = shutil.which("distrobox")
    if not distrobox:
        return False, "distrobox bulunamadı", None

    try:
        # Create distrobox with arch image
        res = subprocess.run(
            [distrobox, "create", "-i", "archlinux:latest", "-n", "pkgforge-build", "--yes"],
            capture_output=True, text=True, timeout=120,
        )
        if res.returncode != 0 and "already exists" not in (res.stderr or ""):
            return False, f"Distrobox oluşturma başarısız: {res.stderr[:200]}", None

        # Copy file and convert
        res = subprocess.run(
            [distrobox, "enter", "pkgforge-build", "--",
             "bash", "-c", f"pacman -Syu --noconfirm && pacman -S --noconfirm debtap && debtap -u && cp /home/*/{deb_path.name} /tmp/ && debtap /tmp/{deb_path.name}"],
            capture_output=True, text=True, timeout=300,
        )
        if res.returncode != 0:
            return False, f"Distrobox dönüşüm başarısız: {res.stderr[:200]}", None

        return True, "Distrobox ile dönüştürüldü", None

    except Exception as exc:
        return False, f"Distrobox hatası: {exc}", None


def smart_convert(
    input_path: Path,
    output_dir: Path,
    tools: ToolPaths,
    preferred_method: str | None = None,
) -> FallbackResult:
    """Try multiple conversion methods automatically.

    Args:
        input_path: Path to the input package file.
        output_dir: Directory to write the output.
        tools: Detected system tools.
        preferred_method: If specified, try this method first.

    Returns:
        FallbackResult with the outcome and full attempt history.
    """
    suffix = input_path.suffix.lower()
    is_deb = suffix == ".deb"
    is_rpm = suffix == ".rpm"

    if not is_deb and not is_rpm:
        return FallbackResult(
            success=False, method="none",
            message=f"Desteklenmeyen format: {suffix}",
        )

    # Build fallback chain based on file type
    if is_deb:
        methods = [
            ("native", _try_native_deb),
            ("debtap", _try_debtap),
            ("docker", _try_docker),
            ("distrobox", _try_distrobox),
        ]
    else:  # RPM
        methods = [
            ("debtap", _try_debtap),
            ("docker", _try_docker),
            ("distrobox", _try_distrobox),
        ]

    # Reorder if preferred method specified
    if preferred_method:
        methods = [(n, f) for n, f in methods if n == preferred_method] + \
                  [(n, f) for n, f in methods if n != preferred_method]

    result = FallbackResult(success=False, method="none", message="Hiçbir yöntem çalışmadı")

    for method_name, method_func in methods:
        log.info("Deneme: %s (%s)", method_name, input_path.name)
        try:
            success, msg, output = method_func(input_path, output_dir, tools)
            result.attempts.append({
                "method": method_name,
                "success": success,
                "message": msg[:200],
            })

            if success and output:
                result.success = True
                result.method = method_name
                result.message = msg
                result.output_pkg = output
                log.info("Başarılı: %s ile %s", method_name, input_path.name)
                break
            else:
                log.info("Başarısız: %s — %s", method_name, msg[:100])
        except Exception as exc:
            result.attempts.append({
                "method": method_name,
                "success": False,
                "message": str(exc)[:200],
            })
            log.warning("Hata: %s — %s", method_name, exc)

    return result
