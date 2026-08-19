"""PkgForge — RPM to DEB Converter.

Extracts RPM package contents and repackages them as a .deb archive.
This enables bidirectional package conversion across distributions.

Flow:
1. Extract RPM via rpm2cpio
2. Parse RPM metadata for control file
3. Create DEBIAN/control
4. Package with dpkg-deb
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from core.security import safe_run

log = logging.getLogger(__name__)


def is_rpm_to_deb_available() -> bool:
    """Check if we can convert RPM to DEB (need rpm2cpio + dpkg-deb)."""
    return bool(shutil.which("rpm2cpio") and shutil.which("dpkg-deb"))


def rpm_to_deb(
    rpm_path: Path,
    output_dir: Path,
) -> tuple[bool, str, Path | None]:
    """Convert an RPM package to a .deb package.

    Args:
        rpm_path: Path to the .rpm file.
        output_dir: Directory to write the .deb file.

    Returns:
        (success, message, deb_path)
    """
    if not rpm_path.is_file():
        return False, f"Dosya bulunamadı: {rpm_path}", None

    if not shutil.which("rpm2cpio"):
        return False, "rpm2cpio bulunamadı — rpmextract paketi gerekli", None

    if not shutil.which("dpkg-deb"):
        return False, "dpkg-deb bulunamadı — dpkg paketi gerekli", None

    with tempfile.TemporaryDirectory(prefix="pkgforge_rpm2deb_") as tmpdir:
        tmp = Path(tmpdir)

        # 1. Extract RPM contents
        pkg_dir = tmp / "pkg_root"
        pkg_dir.mkdir()

        import shlex
        cmd = f"{shlex.quote(shutil.which('rpm2cpio'))} {shlex.quote(str(rpm_path))} | {shlex.quote(shutil.which('bsdtar') or 'bsdtar')} -xf -"
        res = safe_run(["/bin/bash", "-c", cmd], cwd=str(pkg_dir), timeout=60)
        if res.returncode != 0:
            return False, f"RPM çıkarma başarısız: {res.stderr[:200]}", None

        # 2. Get RPM metadata
        rpm_cmd = shutil.which("rpm")
        if rpm_cmd:
            info_res = safe_run(
                [rpm_cmd, "-qp", "--queryformat",
                 "%{NAME}\\n%{VERSION}\\n%{RELEASE}\\n%{ARCH}\\n%{SUMMARY}\\n%{URL}",
                 str(rpm_path)],
                timeout=10,
            )
            lines = info_res.stdout.strip().splitlines() if info_res.returncode == 0 else []
        else:
            lines = []

        name = lines[0] if len(lines) > 0 else rpm_path.stem.split("-")[0]
        version = lines[1] if len(lines) > 1 else "1.0"
        release = lines[2] if len(lines) > 2 else "1"
        arch = lines[3] if len(lines) > 3 else "amd64"
        summary = lines[4] if len(lines) > 4 else f"{name} (converted from RPM)"
        url = lines[5] if len(lines) > 5 else ""

        # Map RPM arch to Debian arch
        arch_map = {"x86_64": "amd64", "noarch": "all", "i686": "i386", "aarch64": "arm64"}
        deb_arch = arch_map.get(arch, arch)

        deb_name = name.lower().replace("_", "-")
        deb_version = f"{version}-{release}"
        output_path = output_dir / f"{deb_name}_{deb_version}_{deb_arch}.deb"

        # 3. Create DEBIAN/control
        deb_root = tmp / "deb"
        deb_root.mkdir()
        debian_dir = deb_root / "DEBIAN"
        debian_dir.mkdir()

        # Calculate installed size
        total_size = sum(f.stat().st_size for f in pkg_dir.rglob("*") if f.is_file())
        installed_kb = max(1, total_size // 1024)

        control = (
            f"Package: {deb_name}\n"
            f"Version: {deb_version}\n"
            f"Architecture: {deb_arch}\n"
            f"Maintainer: PkgForge <noreply@pkgforge.app>\n"
            f"Description: {summary}\n"
            f"Homepage: {url}\n"
            f"Installed-Size: {installed_kb}\n"
        )
        (debian_dir / "control").write_text(control, encoding="utf-8")

        # 4. Copy extracted files
        shutil.copytree(pkg_dir, deb_root / "opt" / deb_name, dirs_exist_ok=True)

        # 5. Build .deb
        res = safe_run(
            ["dpkg-deb", "--build", str(deb_root), str(output_path)],
            timeout=60,
        )
        if res.returncode != 0:
            return False, f"dpkg-deb başarısız: {res.stderr[:200]}", None

        log.info("RPM → DEB dönüştürüldü: %s", output_path)
        return True, f"DEB paketi hazır: {output_path.name}", output_path
