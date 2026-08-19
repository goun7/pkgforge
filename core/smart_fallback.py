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
    """Try building in a Docker container with volume mount for output."""
    docker = shutil.which("docker") or shutil.which("podman")
    if not docker:
        return False, "docker/podman bulunamadı", None

    import tempfile as _tmp
    with _tmp.TemporaryDirectory(prefix="pkgforge_docker_") as tmpdir:
        tmp = Path(tmpdir)

        dockerfile = (
            f"FROM archlinux:latest\n"
            f"RUN pacman -Syu --noconfirm && \\\n"
            f"    pacman -S --noconfirm base-devel debtap sudo && \\\n"
            f"    debtap -u\n"
            f"WORKDIR /build\n"
            f"COPY {deb_path.name} /build/\n"
            f"CMD [\"bash\", \"-c\", \"debtap /build/{deb_path.name} -u && \\\n"
            f"cp *.pkg.tar.zst /output/ 2>/dev/null || \\\n"
            f"cp *.pkg.tar.xz /output/ 2>/dev/null || \\\n"
            f"cp *.pkg.tar /output/ 2>/dev/null || echo NO_OUTPUT\"]\n"
        )
        (tmp / "Dockerfile").write_text(dockerfile)
        shutil.copy2(deb_path, tmp / deb_path.name)

        res = subprocess.run(
            [docker, "build", "-t", "pkgforge-build", str(tmp)],
            capture_output=True, text=True, timeout=300,
        )
        if res.returncode != 0:
            return False, f"Docker build başarısız: {res.stderr[:200]}", None

        res = subprocess.run(
            [docker, "run", "--rm",
             "-v", f"{output_dir}:/output",
             "pkgforge-build"],
            capture_output=True, text=True, timeout=600,
        )
        if res.returncode != 0:
            return False, f"Docker dönüşüm başarısız: {res.stderr[:200]}", None

        for pattern in ["*.pkg.tar.zst", "*.pkg.tar.xz", "*.pkg.tar"]:
            found = list(output_dir.glob(pattern))
            if found:
                output = max(found, key=lambda p: p.stat().st_mtime)
                return True, f"Docker ile dönüştürüldü: {output.name}", output

        return False, "Docker container çıktı üretmedi", None


def _try_distrobox(deb_path: Path, output_dir: Path, tools: ToolPaths) -> tuple[bool, str, Path | None]:
    """Try building in distrobox with home directory sharing."""
    distrobox = shutil.which("distrobox")
    if not distrobox:
        return False, "distrobox bulunamadı", None

    try:
        # Create distrobox (ignore if exists)
        subprocess.run(
            [distrobox, "create", "-i", "archlinux:latest", "-n", "pkgforge-build", "--yes"],
            capture_output=True, text=True, timeout=120,
        )

        # Copy DEB into distrobox home
        container_home = subprocess.run(
            [distrobox, "enter", "pkgforge-build", "--", "echo", "$HOME"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if not container_home:
            container_home = "/root"

        subprocess.run(
            [distrobox, "enter", "pkgforge-build", "--",
             "cp", str(deb_path), f"{container_home}/"],
            capture_output=True, text=True, timeout=30,
        )

        # Install debtap and convert
        build_cmd = (
            f"sudo pacman -Syu --noconfirm && "
            f"sudo pacman -S --noconfirm debtap && "
            f"sudo debtap -u && "
            f"cd {container_home} && debtap {deb_path.name} -u && "
            f"cp {container_home}/*.pkg.tar.* {output_dir}/ 2>/dev/null || true"
        )
        res = subprocess.run(
            [distrobox, "enter", "pkgforge-build", "--", "bash", "-c", build_cmd],
            capture_output=True, text=True, timeout=600,
        )

        if res.returncode != 0:
            return False, f"Distrobox dönüşüm başarısız: {res.stderr[:200]}", None

        for pattern in ["*.pkg.tar.zst", "*.pkg.tar.xz", "*.pkg.tar"]:
            found = list(output_dir.glob(pattern))
            if found:
                output = max(found, key=lambda p: p.stat().st_mtime)
                return True, f"Distrobox ile dönüştürüldü: {output.name}", output

        return False, "Distrobox çıktı üretmedi", None

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
