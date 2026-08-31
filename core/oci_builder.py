"""PkgForge — OCI Container Image Builder.

Converts a .pkg.tar.zst into a standalone OCI container image using
either ``buildah`` (preferred, rootless) or ``podman`` as fallback.

Usage from CLI:
    pkgforge convert --to-oci package.deb
    → produces an OCI image that can be loaded with ``podman load``
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from config import ToolPaths, extract_package_name
from core.security import safe_run
from i18n import tr

log = logging.getLogger(__name__)


def is_container_runtime_available() -> bool:
    """Return True if buildah or podman is available."""
    return bool(shutil.which("buildah") or shutil.which("podman"))


def build_oci_image(
    pkg_path: Path,
    tools: ToolPaths,
    *,
    tag: str | None = None,
    output_file: Path | None = None,
) -> tuple[bool, str, Path | None]:
    """Convert a .pkg.tar.zst to an OCI container image.

    Args:
        pkg_path: Path to the .pkg.tar.zst file.
        tools: Discovered tool paths.
        tag: Docker/OCI image tag. If None, derived from package name.
        output_file: Path to save the OCI tarball. If None, auto-generated.

    Returns:
        (success, message, output_path)
    """
    if not pkg_path.is_file():
        return False, f"Paket dosyası bulunamadı: {pkg_path}", None

    # Determine which container runtime to use
    buildah = shutil.which("buildah")
    podman = shutil.which("podman")

    if not buildah and not podman:
        return (
            False,
            ("Ne buildah ne podman bulundu — OCI görüntü oluşturulamadı. "
             "Kurulum: sudo pacman -S buildah veya podman"),
            None,
        )

    # Derive tag from package filename. Use the authoritative extractor so
    # the tag is the clean package name (hello), not the raw stem which
    # leaves ".pkg.tar" and the version glued on (hello-1.0.0-1-x86_64.pkg.tar).
    if not tag:
        pkg_name = extract_package_name(pkg_path.name)
        tag = f"pkgforge/{pkg_name}:latest"

    if output_file is None:
        output_file = pkg_path.parent / f"{pkg_path.stem}.oci.tar"

    # Use buildah if available (rootless, no daemon needed)
    if buildah:
        return _build_with_buildah(pkg_path, buildah, tag, output_file)
    else:
        return _build_with_podman(pkg_path, podman, tag, output_file)  # type: ignore[arg-type]


def _build_with_buildah(
    pkg_path: Path,
    buildah: str,
    tag: str,
    output_file: Path,
) -> tuple[bool, str, Path | None]:
    """Build OCI image using buildah (rootless, daemonless)."""
    with tempfile.TemporaryDirectory(prefix="pkgforge_oci_"):
        container_name = f"pkgforge-build-{id(pkg_path) % 10000}"

        try:
            # 1. Create a working container from scratch
            res = safe_run(
                [buildah, "from", "--name", container_name, "scratch"],
                timeout=30,
            )
            if res.returncode != 0:
                return False, f"buildah from başarısız: {res.stderr}", None

            # 2. Copy the converted package into the container
            res = safe_run(
                [buildah, "copy", container_name, str(pkg_path), "/pkg/"],
                timeout=60,
            )
            if res.returncode != 0:
                _cleanup_container(buildah, container_name)
                return False, f"buildah copy başarısız: {res.stderr}", None

            # 3. Set the working directory
            safe_run(
                [buildah, "config", "--workingdir", "/pkg", container_name],
                timeout=10,
            )

            # 4. Set metadata
            safe_run(
                [buildah, "config", "--label", f"org.pkgforge.package={pkg_path.name}", container_name],
                timeout=10,
            )

            # 5. Commit to OCI image
            res = safe_run(
                [buildah, "commit", "--format", "oci", container_name, tag],
                timeout=60,
            )
            if res.returncode != 0:
                _cleanup_container(buildah, container_name)
                return False, f"buildah commit başarısız: {res.stderr}", None

            # 6. Export to OCI tarball
            res = safe_run(
                [buildah, "push", "--format", "oci", tag, f"oci:{output_file}"],
                timeout=120,
            )
            if res.returncode != 0:
                _cleanup_container(buildah, container_name)
                return False, f"buildah push başarısız: {res.stderr}", None

            # Cleanup
            _cleanup_container(buildah, container_name)
            safe_run([buildah, "rmi", tag], timeout=30)

            log.info(tr("oci.oci_goruntu_olusturuldu_s_s"), output_file.name, tag)
            return True, f"OCI görüntü hazır: {output_file.name} ({tag})", output_file

        except Exception as exc:  # noqa: BLE001
            _cleanup_container(buildah, container_name)
            return False, f"OCI oluşturma hatası: {exc}", None


def _build_with_podman(
    pkg_path: Path,
    podman: str,
    tag: str,
    output_file: Path,
) -> tuple[bool, str, Path | None]:
    """Build OCI image using podman (needs daemon or rootless)."""
    with tempfile.TemporaryDirectory(prefix="pkgforge_oci_") as tmpdir:
        # Create a temporary Containerfile
        containerfile = Path(tmpdir) / "Containerfile"
        containerfile.write_text(
            f"FROM scratch\n"
            f"COPY {pkg_path.name} /pkg/\n"
            f"WORKDIR /pkg\n"
            f"LABEL org.pkgforge.package={pkg_path.name}\n",
            encoding="utf-8",
        )

        try:
            # Build with podman
            res = safe_run(
                [
                    podman, "build",
                    "--format", "oci",
                    "-t", tag,
                    "-f", str(containerfile),
                    str(pkg_path.parent),
                ],
                timeout=120,
            )
            if res.returncode != 0:
                return False, f"podman build başarısız: {res.stderr}", None

            # Export to OCI tarball
            res = safe_run(
                [podman, "save", "--format", "oci", "-o", str(output_file), tag],
                timeout=120,
            )
            if res.returncode != 0:
                return False, f"podman save başarısız: {res.stderr}", None

            # Cleanup
            safe_run([podman, "rmi", tag], timeout=30)

            log.info(tr("oci.oci_goruntu_olusturuldu_s_s_2"), output_file.name, tag)
            return True, f"OCI görüntü hazır: {output_file.name} ({tag})", output_file

        except Exception as exc:  # noqa: BLE001
            return False, f"OCI oluşturma hatası: {exc}", None


def _cleanup_container(runtime: str, name: str) -> None:
    """Remove a buildah/podman container (best-effort)."""
    safe_run([runtime, "rm", "-f", name], timeout=10)
