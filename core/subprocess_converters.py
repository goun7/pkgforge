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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from core.security import safe_run

from config import ToolPaths

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
            except Exception as exc:
                log.debug("Callback çalıştırılamadı: %s", exc)


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
            from core.package_analyzer import analyze_package
            from core.security import safe_run, check_symlink_attacks, check_dangerous_files
            from core.dependency_resolver import resolve_runtime_dependencies

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
                self.finished.emit(False, f"Güvenlik: symlink saldırısı: {escaping[:3]}", None)
                return

            errors, warnings = check_dangerous_files(src_dir)
            for w in warnings[:5]:
                self._emit(f"⚠ {w}")
            if errors:
                self.finished.emit(False, f"Güvenlik: tehlikeli dosya: {errors[:3]}", None)
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

        except Exception as exc:
            log.error("Native DEB dönüşüm hatası: %s", exc)
            self.finished.emit(False, f"Dönüşüm hatası: {exc}", None)

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

        ar_proc = subprocess.Popen(
            [self._tools.ar, "p", str(deb_path), data_tar],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        tar_cmd = [self._tools.bsdtar, "-xf", "-", "-C", str(dest_dir)]
        tar_proc = subprocess.Popen(
            tar_cmd, stdin=ar_proc.stdout,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if ar_proc.stdout:
            ar_proc.stdout.close()
        tar_proc.communicate(timeout=60)

    def _generate_pkgbuild(self, meta, resolved_deps):
        """Generate PKGBUILD content."""
        import re
        name = re.sub(r"[^a-z0-9@._+-]", "-", meta.name.lower().strip()) or "unknown-deb"
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
        )

        for line in (proc.stdout or []):
            stripped = line.strip()
            if stripped:
                self._emit(f"  {stripped}")

        proc.wait(timeout=600)

        if proc.returncode != 0:
            self.finished.emit(False, f"makepkg başarısız (kod: {proc.returncode})", None)
            return

        # Find output
        pkg_file = None
        for search_dir in [pkg_out, output_dir]:
            if search_dir.is_dir():
                for entry in search_dir.iterdir():
                    if entry.is_file() and ".pkg.tar" in entry.name:
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

    def _do_convert(self, rpm_path: Path, output_dir: Path, meta=None):
        try:
            from core.package_analyzer import analyze_package
            if meta is None:
                meta = analyze_package(rpm_path, self._tools)

            self._emit(f"✓ Paket: {meta.name} {meta.version} ({meta.arch_mapped})")

            # Extract RPM
            pkg_dir = output_dir / "pkg_root"
            pkg_dir.mkdir(parents=True, exist_ok=True)

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
                self.finished.emit(False, f"RPM çıkarma başarısız (kod: {proc.returncode})", None)
                return

            self._emit("✓ RPM içeriği çıkarıldı")

            # Security checks
            from core.security import check_symlink_attacks, check_dangerous_files
            escaping = check_symlink_attacks(pkg_dir)
            if escaping:
                self.finished.emit(False, f"Güvenlik: symlink saldırısı: {escaping[:3]}", None)
                return

            errors, warnings = check_dangerous_files(pkg_dir)
            for w in warnings[:5]:
                self._emit(f"⚠ {w}")
            if errors:
                self.finished.emit(False, f"Güvenlik: tehlikeli dosya: {errors[:3]}", None)
                return

            # Generate PKGBUILD and build
            build_dir = output_dir / "build"
            build_dir.mkdir(parents=True, exist_ok=True)
            src_dir = build_dir / "src"
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

            proc = subprocess.Popen(
                [prog] + args,
                cwd=str(build_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
            for line in (proc.stdout or []):
                stripped = line.strip()
                if stripped:
                    self._emit(f"  {stripped}")
            proc.wait(timeout=600)

            if proc.returncode != 0:
                self.finished.emit(False, f"makepkg başarısız (kod: {proc.returncode})", None)
                return

            # Find output
            pkg_file = None
            for d in [pkg_out, output_dir]:
                if d.is_dir():
                    for entry in d.iterdir():
                        if entry.is_file() and ".pkg.tar" in entry.name:
                            pkg_file = entry
                            break
                if pkg_file:
                    break

            if pkg_file:
                self.finished.emit(True, "RPM dönüşümü başarılı", pkg_file)
            else:
                self.finished.emit(False, "makepkg başarılı ama çıktı paketi bulunamadı", None)

        except Exception as exc:
            self.finished.emit(False, f"Dönüşüm hatası: {exc}", None)

    def _generate_pkgbuild(self, meta, src_dir):
        from core.rpm_converter import _sanitize_pkgname, _sanitize_version, _escape_bash
        from core.dependency_resolver import resolve_runtime_dependencies
        from config import RPM_DEP_MAP

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
