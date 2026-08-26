"""PkgForge — DEB to Arch package converter.

Uses `debtap` (fully automated mode) to convert .deb packages
into Arch-compatible .pkg.tar.zst archives.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from config import ToolPaths

log = logging.getLogger(__name__)


class DebConverter(QObject):
    """Converts a .deb file to .pkg.tar.zst using debtap.

    Signals:
        output_line(str)  – each line of debtap stdout/stderr
        finished(bool, str, Path|None) – success, message, output_pkg
    """

    output_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str, object)  # success, msg, Path|None

    def __init__(
        self,
        tools: ToolPaths,
        parent: QObject | None = None,
        process_factory: Callable[[QObject], QProcess] | None = None,
    ):
        super().__init__(parent)
        self._tools = tools
        # Testler somut QProcess yerine sahte surec enjekte edebilir.
        self._make_process = process_factory or self._default_process
        self._process: QProcess | None = None
        self._output_dir = Path()
        self._cancelled = False

    @staticmethod
    def _default_process(parent: QObject) -> QProcess:
        return QProcess(parent)

    def convert(self, deb_path: Path, output_dir: Path) -> None:
        """Start the debtap conversion asynchronously.

        Args:
            deb_path:   Path to the .deb file.
            output_dir: Directory where the .pkg.tar.zst will be placed.
        """
        if not self._tools.debtap:
            self.finished.emit(False, "debtap bulunamadı — AUR'dan 'debtap' yükleyin", None)
            return

        self._output_dir = output_dir
        self._cancelled = False

        self._process = self._make_process(self)
        self._process.setWorkingDirectory(str(output_dir))

        # Merge stdout and stderr for unified log
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        from core.security import build_sandbox_cmd

        # debtap -Q -o <output_dir> <deb_file>
        raw_cmd = [self._tools.debtap, "-Q", "-o", str(output_dir), str(deb_path)]
        prog, args = build_sandbox_cmd(
            raw_cmd, output_dir, self._tools, extra_ro_binds=[deb_path.parent]
        )

        log.info("Debtap başlatılıyor (%s): %s %s", "sandbox" if prog == self._tools.bwrap else "direct", prog, " ".join(args))
        self.output_line.emit(f"▶ debtap -Q -o {output_dir.name} {deb_path.name}")
        self._process.start(prog, args)


    def cancel(self) -> None:
        """Cancel the running conversion."""
        self._cancelled = True
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self.output_line.emit("⚠ Dönüşüm iptal edildi")

    def _on_output(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            stripped = line.strip()
            if stripped:
                self.output_line.emit(stripped)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._cancelled:
            self.finished.emit(False, "Dönüşüm kullanıcı tarafından iptal edildi", None)
            return

        if exit_code != 0:
            self.finished.emit(
                False,
                f"debtap hata kodu ile çıktı: {exit_code}",
                None,
            )
            return

        # Find the generated .pkg.tar.* file
        pkg_file = self._find_output_package()
        if pkg_file:
            self.output_line.emit(f"✓ Paket oluşturuldu: {pkg_file.name}")
            self.finished.emit(True, "DEB dönüşümü başarılı", pkg_file)
        else:
            self.finished.emit(
                False,
                "debtap başarılı çıktı ama çıktı paketi bulunamadı",
                None,
            )

    def _on_error(self, error: QProcess.ProcessError) -> None:
        error_map = {
            QProcess.ProcessError.FailedToStart: "Debtap başlatılamadı — yol doğru mu?",
            QProcess.ProcessError.Crashed: "Debtap beklenmedik şekilde sonlandı",
            QProcess.ProcessError.Timedout: "Debtap zaman aşımına uğradı",
            QProcess.ProcessError.WriteError: "Debtap'a veri yazılamadı",
            QProcess.ProcessError.ReadError: "Debtap çıktısı okunamadı",
            QProcess.ProcessError.UnknownError: "Bilinmeyen debtap hatası",
        }
        msg = error_map.get(error, f"Debtap hatası: {error}")
        self.finished.emit(False, msg, None)

    def _find_output_package(self) -> Path | None:
        """Find the .pkg.tar.zst (or similar) file produced by debtap."""
        for entry in self._output_dir.iterdir():
            # Exclude metadata sidecars (.sig, .provenance.json, ...) whose
            # names also contain the ".pkg.tar" substring.
            if entry.is_file() and ".pkg.tar" in entry.name and not entry.name.endswith((".sig", ".json")):
                return entry
        return None
