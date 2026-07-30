"""PkgForge — RPM to Arch package converter.

Extracts RPM contents via rpm2cpio and builds a .pkg.tar.zst
package using an auto-generated PKGBUILD + makepkg.
"""

from __future__ import annotations

import logging
import os
import shlex
import textwrap
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from config import RPM_DEP_MAP, ToolPaths
from core.package_analyzer import PackageMetadata
from core.security import check_symlink_attacks
from core.dependency_resolver import resolve_runtime_dependencies

log = logging.getLogger(__name__)


class RpmConverter(QObject):
    """Converts a .rpm file to .pkg.tar.zst via rpm2cpio + makepkg.

    Signals:
        output_line(str)
        finished(bool, str, Path|None)
    """

    output_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str, object)

    def __init__(self, tools: ToolPaths, parent: QObject | None = None):
        super().__init__(parent)
        self._tools = tools
        self._process: QProcess | None = None
        self._work_dir = Path()
        self._meta: PackageMetadata | None = None
        self._cancelled = False
        self._phase = "extract"  # extract → build

    def convert(self, rpm_path: Path, work_dir: Path, meta: PackageMetadata) -> None:
        """Start the RPM conversion pipeline.

        1. Extract RPM contents with rpm2cpio | bsdtar
        2. Generate PKGBUILD
        3. Run makepkg to produce .pkg.tar.zst
        """
        if not self._tools.rpm2cpio:
            self.finished.emit(False, "rpm2cpio bulunamadı — rpmextract paketi gerekli", None)
            return
        if not self._tools.makepkg:
            self.finished.emit(False, "makepkg bulunamadı — pacman paketi gerekli", None)
            return

        self._work_dir = work_dir
        self._meta = meta
        self._cancelled = False
        self._phase = "extract"

        # Phase 1: Extract RPM
        self._extract_rpm(rpm_path)

    def cancel(self) -> None:
        self._cancelled = True
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self.output_line.emit("⚠ RPM dönüşümü iptal edildi")

    # ── Phase 1: Extract ─────────────────────────────────────────

    def _extract_rpm(self, rpm_path: Path) -> None:
        self.output_line.emit("▶ RPM içeriği çıkarılıyor...")

        pkg_dir = self._work_dir / "pkg_root"
        pkg_dir.mkdir(parents=True, exist_ok=True)

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(pkg_dir))
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_extract_finished)
        self._process.errorOccurred.connect(self._on_error)

        # rpm2cpio file.rpm | bsdtar -xf -
        # Build the pipeline with fully quoted arguments so a crafted rpm path
        # cannot break out of the shell command (injection safe).
        cmd = (
            f"{shlex.quote(self._tools.rpm2cpio)} {shlex.quote(str(rpm_path))} "
            f"| {shlex.quote(self._tools.bsdtar)} -xf -"
        )
        self._process.start("/bin/bash", ["-c", cmd])

    def _on_extract_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self._cancelled:
            self.finished.emit(False, "İptal edildi", None)
            return

        if exit_code != 0:
            self.finished.emit(False, f"RPM çıkarma başarısız (kod: {exit_code})", None)
            return

        self.output_line.emit("✓ RPM içeriği çıkarıldı")

        # Security: reject archives whose contents symlink outside the tree
        escaping = check_symlink_attacks(self._work_dir / "pkg_root")
        if escaping:
            self.finished.emit(
                False,
                f"Güvenlik: dizin dışına işaret eden sembolik bağ(lar): {escaping[:3]}",
                None,
            )
            return

        # Phase 2: Generate PKGBUILD and run makepkg
        try:
            self._build_package()
        except Exception as exc:
            self.finished.emit(False, f"PKGBUILD oluşturma hatası: {exc}", None)

    # ── Phase 2: Build ───────────────────────────────────────────

    def _build_package(self) -> None:
        if self._meta is None:
            return

        self.output_line.emit("▶ PKGBUILD oluşturuluyor...")

        build_dir = self._work_dir / "build"
        build_dir.mkdir(parents=True, exist_ok=True)

        # Move extracted files into build/src
        src_dir = build_dir / "src"
        pkg_root = self._work_dir / "pkg_root"
        if pkg_root.exists():
            pkg_root.rename(src_dir)
        else:
            src_dir.mkdir(parents=True, exist_ok=True)

        # Generate PKGBUILD
        pkgbuild_content = self._generate_pkgbuild(src_dir)
        pkgbuild_path = build_dir / "PKGBUILD"
        pkgbuild_path.write_text(pkgbuild_content, encoding="utf-8")
        self.output_line.emit(f"  PKGBUILD yazıldı: {pkgbuild_path.name}")

        # Run makepkg
        self.output_line.emit("▶ makepkg çalıştırılıyor...")
        self._phase = "build"

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(build_dir))
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_build_finished)
        self._process.errorOccurred.connect(self._on_error)

        from core.security import build_sandbox_cmd

        env = QProcess.systemEnvironment()
        env.append(f"PKGDEST={self._work_dir}")
        self._process.setEnvironment(env)

        raw_cmd = [self._tools.makepkg, "-f", "--skipchecksums", "--skipinteg", "--noconfirm"]
        prog, args = build_sandbox_cmd(raw_cmd, build_dir, self._tools)
        self._process.start(prog, args)


    def _on_build_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self._cancelled:
            self.finished.emit(False, "İptal edildi", None)
            return

        if exit_code != 0:
            self.finished.emit(False, f"makepkg başarısız (kod: {exit_code})", None)
            return

        # Find generated package
        pkg_file = self._find_output_package()
        if pkg_file:
            self.output_line.emit(f"✓ Paket oluşturuldu: {pkg_file.name}")
            self.finished.emit(True, "RPM dönüşümü başarılı", pkg_file)
        else:
            self.finished.emit(False, "makepkg başarılı ama çıktı paketi bulunamadı", None)

    def _generate_pkgbuild(self, src_dir: Path) -> str:
        """Generate a PKGBUILD for the extracted RPM content."""
        if self._meta is None:
            return
        meta = self._meta

        # Prefer dependencies resolved from the actual extracted binaries; fall
        # back to the static RPM→Arch name map only if resolution yields nothing.
        resolved = resolve_runtime_dependencies(src_dir, self._tools)
        if resolved:
            deps_str = " ".join(f"'{d}'" for d in resolved)
        else:
            arch_deps = []
            for dep in meta.depends:
                mapped = RPM_DEP_MAP.get(dep, None)
                if mapped:
                    arch_deps.append(f"'{mapped}'")
            deps_str = " ".join(arch_deps) if arch_deps else ""
        name = _sanitize_pkgname(meta.name)
        version = _sanitize_version(meta.version) or "1.0.0"
        arch = meta.arch_mapped or "x86_64"

        return textwrap.dedent(f"""\
            # Auto-generated by PkgForge from RPM
            pkgname='{name}'
            pkgver='{version}'
            pkgrel=1
            pkgdesc='{_escape_bash(meta.description or f"{name} (converted from RPM)")}'
            arch=('{arch}')
            url='{meta.url or "https://unknown"}'
            license=('custom')
            depends=({deps_str})
            options=('!strip' '!emptydirs')

            package() {{
                cp -a "$srcdir"/. "$pkgdir"/
            }}
        """)

    # ── Common ───────────────────────────────────────────────────

    def _on_output(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            stripped = line.strip()
            if stripped:
                self.output_line.emit(stripped)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        error_map = {
            QProcess.ProcessError.FailedToStart: f"{self._phase} işlemi başlatılamadı",
            QProcess.ProcessError.Crashed: f"{self._phase} işlemi çöktü",
            QProcess.ProcessError.Timedout: f"{self._phase} zaman aşımı",
        }
        msg = error_map.get(error, f"Bilinmeyen hata: {error}")
        self.finished.emit(False, msg, None)

    def _find_output_package(self) -> Path | None:
        for entry in self._work_dir.iterdir():
            if entry.is_file() and ".pkg.tar" in entry.name:
                return entry
        return None


def _sanitize_pkgname(name: str) -> str:
    """Sanitize a package name for PKGBUILD."""
    import re
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9@._+-]", "-", name)
    return name or "unknown-pkg"


def _sanitize_version(version: str) -> str:
    """Sanitize a version string (remove epoch, release suffixes)."""
    import re
    # Remove epoch (e.g., "1:" prefix)
    version = re.sub(r"^\d+:", "", version)
    # Remove Debian/RPM release suffix after last '-'
    if "-" in version:
        version = version.rsplit("-", 1)[0]
    # Only keep valid chars
    version = re.sub(r"[^a-zA-Z0-9.+~]", ".", version)
    return version or "1.0.0"


def _escape_bash(text: str) -> str:
    """Escape single quotes for bash."""
    return text.replace("'", "'\\''")
