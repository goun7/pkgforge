"""PkgForge — Native Pure Python DEB to Arch package converter.

Extracts DEB contents directly using tar/bsdtar/ar, generates a clean
PKGBUILD, and builds .pkg.tar.zst via makepkg in seconds without relying on debtap.
"""

from __future__ import annotations

import logging
import re
import textwrap
import subprocess
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from config import ToolPaths, DEB_ARCH_MAP
from core.package_analyzer import PackageMetadata, analyze_package
from core.security import (
    build_sandbox_cmd,
    check_dangerous_files,
    check_symlink_attacks,
    safe_run,
)
from core.dependency_resolver import resolve_runtime_dependencies

log = logging.getLogger(__name__)


class NativeDebConverter(QObject):
    """Converts .deb files natively to Arch Linux packages via auto-generated PKGBUILD."""

    output_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str, object)  # success, msg, output_pkg

    def __init__(self, tools: ToolPaths, parent: QObject | None = None):
        super().__init__(parent)
        self._tools = tools
        self._process: QProcess | None = None
        self._work_dir = Path()
        self._meta: PackageMetadata | None = None
        self._cancelled = False

    def convert(self, deb_path: Path, output_dir: Path) -> None:
        """Start high-speed native DEB conversion."""
        if not deb_path.is_file():
            self.finished.emit(False, f"DEB dosyası bulunamadı: {deb_path}", None)
            return

        if not self._tools.makepkg:
            self.finished.emit(False, "makepkg bulunamadı", None)
            return

        self._work_dir = output_dir
        self._cancelled = False

        self.output_line.emit("▶ Paket analizi yapılıyor...")
        try:
            self._meta = analyze_package(deb_path, self._tools)
        except Exception as exc:
            self.finished.emit(False, f"DEB analizi başarısız: {exc}", None)
            return

        self.output_line.emit("▶ DEB verileri ayıklanıyor...")
        try:
            build_dir = self._work_dir / "native_build"
            src_dir = build_dir / "src"
            src_dir.mkdir(parents=True, exist_ok=True)

            self._extract_data_tar(deb_path, src_dir)

            # Security: reject archives whose contents symlink outside the tree
            escaping = check_symlink_attacks(src_dir)
            if escaping:
                raise RuntimeError(
                    f"Güvenlik: dizin dışına işaret eden sembolik bağ(lar): {escaping[:3]}"
                )

            # Security: flag setuid binaries, device nodes and suspicious ELF
            errors, warnings = check_dangerous_files(src_dir)
            for warn in warnings[:5]:
                self.output_line.emit(f"⚠ {warn}")
            if errors:
                raise RuntimeError(
                    f"Güvenlik: tehlikeli dosya özellikleri: {errors[:3]}"
                )

            # Resolve real Arch dependencies from the extracted binaries so the
            # generated package declares installable deps, not raw deb names.
            self.output_line.emit("▶ Bağımlılıklar çözümleniyor...")
            resolved_deps = resolve_runtime_dependencies(src_dir, self._tools)
            if resolved_deps:
                self.output_line.emit(f"  {len(resolved_deps)} bağımlılık çözümlendi")

            pkgbuild_content = self._generate_pkgbuild(self._meta, resolved_deps)

            pkgbuild_path = build_dir / "PKGBUILD"
            pkgbuild_path.write_text(pkgbuild_content, encoding="utf-8")
            self.output_line.emit(f"  PKGBUILD oluşturuldu: {pkgbuild_path.name}")

            self._run_makepkg(build_dir)

        except Exception as exc:
            log.error("Native DEB dönüşüm hatası: %s", exc)
            self.finished.emit(False, f"Dönüşüm hatası: {exc}", None)

    def cancel(self) -> None:
        self._cancelled = True
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self.output_line.emit("⚠ Native DEB dönüşümü iptal edildi")

    def _extract_data_tar(self, deb_path: Path, dest_dir: Path) -> None:
        """Extract data.tar.* member from .deb into dest_dir."""
        # Find data.tar.* using ar t
        ar_res = safe_run([self._tools.ar, "t", str(deb_path)])
        if ar_res.returncode != 0:
            raise RuntimeError(f"ar başarısız: {ar_res.stderr}")

        data_tar = None
        for member in ar_res.stdout.splitlines():
            if member.strip().startswith("data.tar"):
                data_tar = member.strip()
                break

        if not data_tar:
            raise RuntimeError(".deb içinde data.tar bulunamadı")

        # Extract data.tar payload and pipe to bsdtar or tar.
        # ar_proc.stderr is consumed via PIPE to avoid a deadlock if ar
        # fills the OS pipe buffer while nobody reads stderr.
        ar_proc = subprocess.Popen(
            [self._tools.ar, "p", str(deb_path), data_tar],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        tar_cmd = [self._tools.bsdtar, "-xf", "-", "-C", str(dest_dir)] if self._tools.bsdtar else ["tar", "-xf", "-", "-C", str(dest_dir)]
        tar_proc = subprocess.Popen(
            tar_cmd,
            stdin=ar_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Close our copy of ar's stdout so tar sees EOF; read ar's stderr
        # in parallel so the pipe buffer never fills up.
        if ar_proc.stdout:
            ar_proc.stdout.close()
        ar_stderr = ar_proc.stderr.read() if ar_proc.stderr else b""
        ar_proc.wait(timeout=30)

        _stdout, stderr = tar_proc.communicate(timeout=60)
        if ar_proc.returncode != 0:
            raise RuntimeError(
                f"ar başarısız (kod: {ar_proc.returncode}): "
                f"{ar_stderr.decode('utf-8', errors='replace')}"
            )
        if tar_proc.returncode != 0:
            raise RuntimeError(f"İçerik çıkarılamadı: {stderr.decode('utf-8', errors='replace')}")

    def _generate_pkgbuild(self, meta: PackageMetadata, resolved_deps: list[str] | None = None) -> str:
        """Generate Arch Linux PKGBUILD for extracted DEB contents."""
        name = _sanitize_pkgname(meta.name)
        version = _sanitize_version(meta.version)
        arch = meta.arch_mapped or "x86_64"

        # Sanitize description for shell safety inside PKGBUILD single-quoted strings
        raw_desc = meta.description or f"{name} (converted from DEB)"
        desc = raw_desc.replace('`', '').replace('$(', '').replace("'", "'\\''")
        url = meta.url if meta.url else "https://archlinux.org"

        # Prefer dependencies resolved to real Arch packages. If resolution
        # produced nothing, declare no deps (an empty depends() still installs;
        # emitting raw deb names would make `pacman -U` fail).
        if resolved_deps:
            deps_str = " ".join(f"'{d}'" for d in resolved_deps)
        else:
            deps_str = ""

        return textwrap.dedent(f"""\
            # Auto-generated by PkgForge Native DEB Converter
            pkgname='{name}'
            pkgver='{version}'
            pkgrel=1
            pkgdesc='{desc}'
            arch=('{arch}')
            url='{url}'
            license=('custom')
            depends=({deps_str})
            options=('!strip' '!emptydirs')

            package() {{
                # Ownership is set by pacman at install time; not preserving it
                # also keeps the build working inside sandboxes/user namespaces
                # where chown to other uids fails (EINVAL).
                cp -a --no-preserve=ownership "$srcdir"/. "$pkgdir"/
            }}
        """)

    def _run_makepkg(self, build_dir: Path) -> None:
        """Run makepkg in build_dir."""
        self.output_line.emit("▶ makepkg paketi derliyor...")

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(build_dir))
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_makepkg_finished)
        self._process.errorOccurred.connect(self._on_error)

        # PKGDEST must point inside build_dir: that is the directory bound into
        # the bwrap sandbox. Pointing it at a parent dir would write into the
        # sandbox's private tmpfs, and the package would vanish on exit.
        pkg_out = build_dir / "pkgout"
        pkg_out.mkdir(parents=True, exist_ok=True)

        from PyQt6.QtCore import QProcessEnvironment
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PKGDEST", str(pkg_out))
        self._process.setProcessEnvironment(env)

        raw_cmd = [self._tools.makepkg, "-f", "--skipchecksums", "--skipinteg", "--noconfirm"]
        prog, args = build_sandbox_cmd(raw_cmd, build_dir, self._tools)
        self._process.start(prog, args)

    def _on_output(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            stripped = line.strip()
            if stripped:
                self.output_line.emit(f"  {stripped}")

    def _on_makepkg_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self._cancelled:
            self.finished.emit(False, "İptal edildi", None)
            return

        if exit_code != 0:
            self.finished.emit(False, f"makepkg başarısız (kod: {exit_code})", None)
            return

        # Find output package
        pkg_file = self._find_output_package()
        if pkg_file:
            self.output_line.emit(f"✓ Native DEB paketi hazırlandı: {pkg_file.name}")
            self.finished.emit(True, "Native DEB dönüşümü başarılı", pkg_file)
        else:
            self.finished.emit(False, "makepkg başarılı ancak çıktı paketi bulunamadı", None)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        self.finished.emit(False, f"Native DEB dönüştürücü hatası: {error}", None)

    def _find_output_package(self) -> Path | None:
        # PKGDEST is native_build/pkgout (sandbox-bound); also tolerate the
        # legacy work_dir location in case PKGDEST was not honored.
        search_dirs = [self._work_dir / "native_build" / "pkgout", self._work_dir]
        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            for entry in search_dir.iterdir():
                if entry.is_file() and ".pkg.tar" in entry.name:
                    return entry
        return None


def _sanitize_pkgname(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9@._+-]", "-", name)
    return name or "unknown-deb-pkg"


def _sanitize_version(version: str) -> str:
    version = re.sub(r"^\d+:", "", version)
    if "-" in version:
        version = version.rsplit("-", 1)[0]
    version = re.sub(r"[^a-zA-Z0-9.+~]", ".", version)
    return version or "1.0.0"
