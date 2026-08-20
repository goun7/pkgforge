"""PkgForge — Package installer.

Handles privileged package installation via Polkit (pkexec)
and post-installation verification.
"""

from __future__ import annotations

import logging
import shlex
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from config import ToolPaths
from core.security import safe_run

log = logging.getLogger(__name__)

# The install helper script that pkexec will execute
INSTALL_HELPER = Path(__file__).resolve().parent.parent / "scripts" / "install_helper.sh"


class Installer(QObject):
    """Install a .pkg.tar.zst package using pkexec + pacman -U.

    Signals:
        output_line(str)
        finished(bool, str)  – success, message
    """

    output_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, tools: ToolPaths, parent: QObject | None = None):
        super().__init__(parent)
        self._tools = tools
        self._process: QProcess | None = None
        self._pkg_name = ""
        self._cancelled = False
        self._snapshot_name = ""

    def install(self, pkg_path: Path, pkg_name: str) -> None:
        """Install the package using pkexec + install_helper.sh.

        Args:
            pkg_path: Path to the .pkg.tar.zst file.
            pkg_name: Expected package name for post-install verification.
        """
        if not pkg_path.is_file():
            self.finished.emit(False, f"Paket dosyası bulunamadı: {pkg_path}")
            return

        if not self._tools.pkexec:
            self.finished.emit(False, "pkexec bulunamadı — polkit paketi gerekli")
            return

        # Validate that the file has the expected extension
        if ".pkg.tar" not in pkg_path.name:
            self.finished.emit(False, f"Geçersiz paket dosyası: {pkg_path.name}")
            return

        self._pkg_name = pkg_name
        self._cancelled = False

        self.output_line.emit(f"▶ Paket kuruluyor: {pkg_path.name}")

        # Take a filesystem snapshot before installation (best-effort)
        from i18n import load_setting
        if load_setting("snapshot", True):
            try:
                from core.snapshot_manager import take_snapshot, detect_backend
                backend = detect_backend()
                if backend != "none":
                    self.output_line.emit(f"  📸 {backend.upper()} snapshot alınıyor...")
                    snap = take_snapshot(pkg_name)
                    if snap.success:
                        self._snapshot_name = snap.snapshot_name
                        self.output_line.emit(f"  ✓ Snapshot hazır: {snap.snapshot_name}")
                    else:
                        self._snapshot_name = ""
                        self.output_line.emit(f"  ⚠ {snap.detail}")
                else:
                    self._snapshot_name = ""
            except Exception as exc:
                log.debug("Snapshot temizleme başarısız: %s", exc)
                self._snapshot_name = ""
        else:
            self._snapshot_name = ""

        self.output_line.emit("  Yetki yükseltme isteniyor (Polkit)...")

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        # Use install_helper.sh for additional safety layer
        if INSTALL_HELPER.is_file():
            self._process.start(
                self._tools.pkexec,
                ["/bin/bash", str(INSTALL_HELPER), str(pkg_path)],
            )
        else:
            # Direct pkexec pacman -U fallback (-- guards against a package
            # path being parsed as a pacman option)
            self._process.start(
                self._tools.pkexec,
                [self._tools.pacman, "-U", "--noconfirm", "--", str(pkg_path)],
            )

    def cancel(self) -> None:
        """Cancel the ongoing installation."""
        self._cancelled = True
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self.output_line.emit("⚠ Kurulum iptal edildi")

    def _on_output(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            stripped = line.strip()
            if stripped:
                self.output_line.emit(f"  {stripped}")

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self._cancelled:
            self.finished.emit(False, "Kurulum kullanıcı tarafından iptal edildi")
            return

        if exit_code != 0:
            snap_hint = f"\n  📸 Snapshot mevcut: {self._snapshot_name}" if self._snapshot_name else ""
            if exit_code == 126:
                self.finished.emit(False, f"Yetkilendirme reddedildi (Polkit){snap_hint}")
            elif exit_code == 127:
                self.finished.emit(False, f"pkexec komutu bulunamadı{snap_hint}")
            else:
                self.finished.emit(False, f"Kurulum başarısız (kod: {exit_code}){snap_hint}")
            return

        # Post-install verification
        verified = self._verify_installation()
        if verified:
            snap_hint = f" [snapshot: {self._snapshot_name}]" if self._snapshot_name else ""
            self.output_line.emit(f"✓ {self._pkg_name} başarıyla kuruldu/güncellendi{snap_hint}")
            self.finished.emit(True, f"{self._pkg_name} başarıyla kuruldu")
        else:
            self.output_line.emit("⚠ Kurulum tamamlandı ama doğrulama başarısız")
            self.finished.emit(True, "Kurulum tamamlandı (doğrulama yapılamadı)")

    def _on_error(self, error: QProcess.ProcessError) -> None:
        error_map = {
            QProcess.ProcessError.FailedToStart: "pkexec başlatılamadı",
            QProcess.ProcessError.Crashed: "Kurulum işlemi çöktü",
            QProcess.ProcessError.Timedout: "Kurulum zaman aşımı",
        }
        msg = error_map.get(error, f"Kurulum hatası: {error}")
        self.finished.emit(False, msg)

    def _verify_installation(self) -> bool:
        """Verify the package was installed successfully."""
        # The name comes from untrusted package metadata; validate before
        # passing to pacman so a crafted name cannot inject CLI options.
        from core.security import is_valid_package_name
        if not is_valid_package_name(self._pkg_name):
            return False

        result = safe_run(
            [self._tools.pacman, "-Qi", self._pkg_name],
            timeout=10,
        )
        return result.returncode == 0
