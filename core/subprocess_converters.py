"""PkgForge — Subprocess-based converters for CLI mode.

Drop-in replacements for the Qt-based converters that use Python's
stdlib ``subprocess`` module instead of ``QProcess``.  This allows the
CLI to run without PyQt6 installed.

These converters expose the same ``convert()`` / ``output_line`` /
``finished`` interface as the Qt versions so ``cli_bridge.py`` can
use either backend transparently.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from config import ToolPaths
from core.security import safe_run
from i18n import tr

log = logging.getLogger(__name__)


# ── Signal-like callback system ─────────────────────────────────

class Signal:
    """Lightweight signal/slot replacement for subprocess converters.

    Connects callbacks and emits them in the caller's thread.
    """

    def __init__(self):
        self._callbacks: list[Callable] = []

    def connect(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback: Callable) -> None:
        self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    def emit(self, *args) -> None:
        for cb in self._callbacks:
            try:
                cb(*args)
            except Exception as exc:  # noqa: BLE001
                log.debug(tr("subconv.callback_calistirilamadi_s"), exc)


# ── Native DEB Converter (subprocess) ──────────────────────────

class NativeDebConverterSubprocess:
    """Converts .deb files natively using subprocess (no PyQt6)."""

    def __init__(self, tools: ToolPaths, parent=None):
        self._tools = tools
        self._cancelled = False
        self.output_line = Signal()
        self.finished = Signal()

    def convert(self, deb_path: Path, output_dir: Path) -> None:
        """Start conversion in a background thread."""
        t = threading.Thread(target=self._do_convert, args=(deb_path, output_dir), daemon=True)
        t.start()

    def cancel(self):
        self._cancelled = True

    def _emit(self, msg: str):
        self.output_line.emit(msg)

    def _do_convert(self, deb_path: Path, output_dir: Path) -> None:
        """Run the full conversion synchronously."""
        try:
            from core.dep_resolver import resolve_runtime_dependencies
            from core.package_analyzer import analyze_package
            from core.security import (
                check_dangerous_files,
                check_symlink_attacks,
            )

            meta = analyze_package(deb_path, self._tools)
            self._emit(f"✓ Paket: {meta.name} {meta.version} ({meta.arch_mapped})")

            # Extract
            build_dir = output_dir / "native_build"
            src_dir = build_dir / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            self._extract_data_tar(deb_path, src_dir)

            # Security
            escaping = check_symlink_attacks(src_dir)
            if escaping:
                self.finished.emit(False, tr("subconv.guvenlik_symlink_saldirisi_escaping_2", escaping=escaping[:3]), None)
                return

            errors, warnings = check_dangerous_files(src_dir)
            for w in warnings[:5]:
                self._emit(f"⚠ {w}")
            if errors:
                self.finished.emit(False, tr("subconv.guvenlik_tehlikeli_dosya_errors_2", errors=errors[:3]), None)
                return

            # Resolve deps
            self._emit("▶ Bağımlılıklar çözümleniyor...")
            resolved_deps = resolve_runtime_dependencies(src_dir, self._tools)

            # Generate PKGBUILD
            pkgbuild = self._generate_pkgbuild(meta, resolved_deps)
            pkgbuild_path = build_dir / "PKGBUILD"
            pkgbuild_path.write_text(pkgbuild, encoding="utf-8")
            self._emit("  PKGBUILD oluşturuldu")

            # Run makepkg
            self._run_makepkg(build_dir, output_dir)

        except Exception as exc:  # noqa: BLE001
            log.error(tr("subconv.native_deb_donusum_hatasi_s"), exc)
            self.finished.emit(False, tr("subconv.donusum_hatasi_exc_2", exc=exc), None)

    def _extract_data_tar(self, deb_path: Path, dest_dir: Path):
        """Extract data.tar.* from DEB."""
        ar_res = safe_run(
            [self._tools.ar, "t", str(deb_path)], timeout=30,
        )
        data_tar = None
        for m in ar_res.stdout.splitlines():
            if m.strip().startswith("data.tar"):
                data_tar = m.strip()
                break
        if not data_tar:
            raise RuntimeError(".deb içinde data.tar bulunamadı")

        # ar stderr'sini paralel oku: boru tam dolarsa ar bloklanmasin
        # (native_deb_converter'daki ayni desenle parite).
        ar_proc = subprocess.Popen(
            [self._tools.ar, "p", str(deb_path), data_tar],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        tar_cmd = [self._tools.bsdtar, "-xf", "-", "-C", str(dest_dir)]
        tar_proc = subprocess.Popen(
            tar_cmd, stdin=ar_proc.stdout,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        # Kendi ar.stdout kopyamizi kapat ki tar EOF gorsun.
        if ar_proc.stdout:
            ar_proc.stdout.close()
        ar_stderr = ar_proc.stderr.read() if ar_proc.stderr else b""
        ar_proc.wait(timeout=30)
        _stdout, stderr = tar_proc.communicate(timeout=60)
        if ar_proc.returncode != 0:
            raise RuntimeError(
                tr("subconv.ar_basarisiz_kod_ar", ar_proc_returncode=ar_proc.returncode, ar_stderr_decode=ar_stderr.decode('utf-8', errors='replace'))
            )
        if tar_proc.returncode != 0:
            raise RuntimeError(
                tr("subconv.cerik_cikarilamadi_stderr_decode", stderr_decode=stderr.decode('utf-8', errors='replace'))
            )

    def _generate_pkgbuild(self, meta, resolved_deps):
        """Generate PKGBUILD content."""
        import re
        name = (re.sub(r"[^a-z0-9@._+-]", "-",
                       meta.name.lower().strip()).strip("-")) or "unknown-deb"
        version = re.sub(r"^\d+:", "", meta.version)
        if "-" in version:
            version = version.rsplit("-", 1)[0]
        version = re.sub(r"[^a-zA-Z0-9.+~]", ".", version) or "1.0.0"
        arch = meta.arch_mapped or "x86_64"
        desc = (meta.description or f"{name} (converted from DEB)").replace("'", "'\\''")
        deps = " ".join(f"'{d}'" for d in (resolved_deps or []))

        return f"""\
# Auto-generated by PkgForge
pkgname='{name}'
pkgver='{version}'
pkgrel=1
pkgdesc='{desc}'
arch=('{arch}')
url='{meta.url or "https://archlinux.org"}'
license=('custom')
depends=({deps})
options=('!strip' '!emptydirs')

package() {{
    cp -a --no-preserve=ownership "$srcdir"/. "$pkgdir"/
}}
"""

    def _run_makepkg(self, build_dir: Path, output_dir: Path):
        """Run makepkg via subprocess."""
        pkg_out = build_dir / "pkgout"
        pkg_out.mkdir(parents=True, exist_ok=True)

        self._emit("▶ makepkg paketi derliyor...")
        env = {
            **os.environ,
            "PKGDEST": str(pkg_out),
        }

        raw_cmd = [self._tools.makepkg, "-f", "--skipchecksums", "--skipinteg", "--noconfirm"]

        # Check if sandbox is available
        from core.security import build_sandbox_cmd
        prog, args = build_sandbox_cmd(raw_cmd, build_dir, self._tools)

        proc = subprocess.Popen(
            [prog] + args,
            cwd=str(build_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        for line in (proc.stdout or []):
            stripped = line.strip()
            if stripped:
                self._emit(f"  {stripped}")

        proc.wait(timeout=600)

        if proc.returncode != 0:
            self.finished.emit(False, tr("subconv.makepkg_basarisiz_kod_proc", proc_returncode=proc.returncode), None)
            return

        # Find output
        pkg_file = None
        for search_dir in [pkg_out, output_dir]:
            if search_dir.is_dir():
                for entry in search_dir.iterdir():
                    if entry.is_file() and ".pkg.tar" in entry.name and not entry.name.endswith((".sig", ".json")):
                        pkg_file = entry
                        break
            if pkg_file:
                break

        if pkg_file:
            self.finished.emit(True, "Native DEB dönüşümü başarılı", pkg_file)
        else:
            self.finished.emit(False, "makepkg başarılı ama çıktı paketi bulunamadı", None)


# ── RPM Converter (subprocess) ─────────────────────────────────

class RpmConverterSubprocess:
    """Converts .rpm files using subprocess (no PyQt6)."""

    def __init__(self, tools: ToolPaths, parent=None):
        self._tools = tools
        self._cancelled = False
        self.output_line = Signal()
        self.finished = Signal()

    def convert(self, rpm_path: Path, output_dir: Path, meta=None) -> None:
        t = threading.Thread(target=self._do_convert, args=(rpm_path, output_dir, meta), daemon=True)
        t.start()

    def cancel(self):
        self._cancelled = True

    def _emit(self, msg: str):
        self.output_line.emit(msg)

    def _rpm_extract(self, rpm_path: Path, pkg_dir: Path) -> tuple[bool, str]:
        """RPM icerigini rpm2cpio | bsdtar ile cikarir.

        Guvenlik notu: komut shlex.quote ile kurulur; boru bilincli
        olarak /bin/bash -c uzerinden kurulur.
        """
        self._emit("▶ RPM içeriği çıkarılıyor...")
        import shlex
        cmd = (
            f"{shlex.quote(self._tools.rpm2cpio)} {shlex.quote(str(rpm_path))} "
            f"| {shlex.quote(self._tools.bsdtar)} -xf -"
        )
        proc = subprocess.Popen(
            ["/bin/bash", "-c", cmd],
            cwd=str(pkg_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.communicate(timeout=60)
        if proc.returncode != 0:
            return False, tr("subconv.rpm_cikarma_basarisiz_kod", proc_returncode=proc.returncode)
        self._emit("✓ RPM içeriği çıkarıldı")
        return True, ""

    def _rpm_security_gate(self, pkg_dir: Path) -> tuple[bool, str]:
        """Symlink saldirisi + tehlikeli dosya kontrolleri (fail-closed).

        Uyarilar akisa basilir; hatalar donusumu keser.
        """
        from core.security import check_dangerous_files, check_symlink_attacks
        escaping = check_symlink_attacks(pkg_dir)
        if escaping:
            return False, tr("subconv.guvenlik_symlink_saldirisi_escaping", escaping=escaping[:3])

        errors, warnings = check_dangerous_files(pkg_dir)
        for w in warnings[:5]:
            self._emit(f"⚠ {w}")
        if errors:
            return False, tr("subconv.guvenlik_tehlikeli_dosya_errors", errors=errors[:3])
        return True, ""

    def _rpm_makepkg_build(self, meta, output_dir: Path) -> tuple[bool, str]:
        """PKGBUILD uret ve sandbox icinde makepkg ile paketi kur.

        makepkg ciktisi satir satir akisa yansitilir.
        """
        build_dir = output_dir / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        src_dir = build_dir / "src"
        pkg_dir = output_dir / "pkg_root"
        if pkg_dir.exists():
            pkg_dir.rename(src_dir)
        else:
            src_dir.mkdir(parents=True, exist_ok=True)

        self._emit("▶ PKGBUILD oluşturuluyor...")
        pkgbuild = self._generate_pkgbuild(meta, src_dir)
        (build_dir / "PKGBUILD").write_text(pkgbuild, encoding="utf-8")

        self._emit("▶ makepkg çalıştırılıyor...")
        pkg_out = build_dir / "pkgout"
        pkg_out.mkdir(parents=True, exist_ok=True)

        import os
        env = {**os.environ, "PKGDEST": str(pkg_out)}
        from core.security import build_sandbox_cmd
        raw_cmd = [self._tools.makepkg, "-f", "--skipchecksums", "--skipinteg", "--noconfirm"]
        prog, args = build_sandbox_cmd(raw_cmd, build_dir, self._tools)

        build_proc = subprocess.Popen(
            [prog] + args,
            cwd=str(build_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in (build_proc.stdout or []):
            stripped = line.strip()
            if stripped:
                self._emit(f"  {stripped}")
        build_proc.wait(timeout=600)

        if build_proc.returncode != 0:
            return False, tr("subconv.makepkg_basarisiz_kod_build", build_proc_returncode=build_proc.returncode)
        return True, ""

    @staticmethod
    def _find_pkg_artifact(pkg_dir: Path, output_dir: Path) -> Path | None:
        """PKGDEST ve cikis dizininde .pkg.tar urunu arar."""
        pkg_file = None
        for d in [pkg_dir, output_dir]:
            if d.is_dir():
                for entry in d.iterdir():
                    if entry.is_file() and ".pkg.tar" in entry.name and not entry.name.endswith((".sig", ".json")):
                        pkg_file = entry
                        break
            if pkg_file:
                break
        return pkg_file

    def _do_convert(self, rpm_path: Path, output_dir: Path, meta=None):
        try:
            from core.package_analyzer import analyze_package
            if meta is None:
                meta = analyze_package(rpm_path, self._tools)

            self._emit(f"✓ Paket: {meta.name} {meta.version} ({meta.arch_mapped})")

            pkg_dir = output_dir / "pkg_root"
            pkg_dir.mkdir(parents=True, exist_ok=True)

            ok, msg = self._rpm_extract(rpm_path, pkg_dir)
            if not ok:
                self.finished.emit(False, msg, None)
                return

            ok, msg = self._rpm_security_gate(pkg_dir)
            if not ok:
                self.finished.emit(False, msg, None)
                return

            ok, msg = self._rpm_makepkg_build(meta, output_dir)
            if not ok:
                self.finished.emit(False, msg, None)
                return

            pkg_file = self._find_pkg_artifact(output_dir / "build" / "pkgout", output_dir)
            if pkg_file:
                self.finished.emit(True, "RPM dönüşümü başarılı", pkg_file)
            else:
                self.finished.emit(False, "makepkg başarılı ama çıktı paketi bulunamadı", None)

        except Exception as exc:  # noqa: BLE001
            self.finished.emit(False, tr("subconv.donusum_hatasi_exc", exc=exc), None)

    def _generate_pkgbuild(self, meta, src_dir):
        from config import RPM_DEP_MAP
        from core.dep_resolver import resolve_runtime_dependencies
        from core.rpm_converter import (
            _escape_bash,
            _sanitize_pkgname,
            _sanitize_version,
        )

        resolved = resolve_runtime_dependencies(src_dir, self._tools)
        if resolved:
            deps_str = " ".join(f"'{d}'" for d in resolved)
        else:
            arch_deps = []
            for dep in meta.depends:
                mapped = RPM_DEP_MAP.get(dep)
                if mapped:
                    arch_deps.append(f"'{mapped}'")
            deps_str = " ".join(arch_deps) if arch_deps else ""

        name = _sanitize_pkgname(meta.name)
        version = _sanitize_version(meta.version) or "1.0.0"
        arch = meta.arch_mapped or "x86_64"
        desc = _escape_bash(meta.description or f"{name} (converted from RPM)")

        return f"""\
# Auto-generated by PkgForge from RPM
pkgname='{name}'
pkgver='{version}'
pkgrel=1
pkgdesc='{desc}'
arch=('{arch}')
url='{meta.url or "https://unknown"}'
license=('custom')
depends=({deps_str})
options=('!strip' '!emptydirs')

package() {{
    cp -a --no-preserve=ownership "$srcdir"/. "$pkgdir"/
}}
"""
