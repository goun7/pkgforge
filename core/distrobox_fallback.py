"""PkgForge — Distrobox container fallback.

When native compatibility checks fail, offers to install the package
inside a Distrobox (Ubuntu/Debian) container and export the desktop
entry to the host system.
"""

from __future__ import annotations

import logging
import re
import shlex
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from config import ToolPaths

log = logging.getLogger(__name__)

# Container name prefix
_CONTAINER_PREFIX = "pkgforge"


class DistroboxFallback(QObject):
    """Manages Distrobox container creation and package installation.

    Signals:
        output_line(str)
        finished(bool, str) – success, message
    """

    output_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, tools: ToolPaths, parent: QObject | None = None):
        super().__init__(parent)
        self._tools = tools
        self._process: QProcess | None = None
        self._pkg_name = ""
        self._pkg_path = Path()
        self._container_name = ""
        self._phase = ""

    @staticmethod
    def is_available(tools: ToolPaths) -> bool:
        """Check if distrobox is available on the system."""
        return tools.has_distrobox

    def install_in_container(
        self, pkg_path: Path, pkg_name: str, pkg_type: str = "deb"
    ) -> None:
        """Install package in a Distrobox container.

        Steps:
        1. Create container (Ubuntu for .deb, Fedora for .rpm)
        2. Copy package into container
        3. Install package inside container
        4. Export desktop entry to host
        """
        if not self._tools.distrobox:
            self.finished.emit(False, "distrobox bulunamadı")
            return

        self._pkg_name = pkg_name
        self._pkg_path = pkg_path
        # Distrobox container names allow only [a-zA-Z0-9._-]; sanitize the
        # package name so a crafted name can neither break creation nor be
        # smuggled into the shell command below.
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "-", pkg_name).strip("-") or "pkg"
        self._container_name = f"{_CONTAINER_PREFIX}-{safe_name}"

        image = "ubuntu:latest" if pkg_type == "deb" else "fedora:latest"
        self._phase = "create"
        self.output_line.emit(f"▶ Container oluşturuluyor: {self._container_name} ({image})")

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_create_finished)
        self._process.errorOccurred.connect(self._on_error)

        self._process.start(self._tools.distrobox, [
            "create",
            "--name", self._container_name,
            "--image", image,
            "--yes",
        ])

    def _on_create_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if exit_code != 0:
            self.finished.emit(False, f"Container oluşturulamadı (kod: {exit_code})")
            return

        self.output_line.emit("✓ Container oluşturuldu")
        self._phase = "install"
        self._install_in_container()

    def _install_in_container(self) -> None:
        """Install the package inside the container."""
        self.output_line.emit(f"▶ Paket container içinde kuruluyor...")

        pkg_type = "deb" if self._pkg_path.suffix.lower() == ".deb" else "rpm"

        # Quote every package-derived value so a malicious filename cannot
        # inject arbitrary shell commands. Use a hard-to-guess suffix so an
        # attacker cannot pre-create a symlink at the target path (CWE-377).
        import hashlib
        import os
        unique = hashlib.sha256(f"{os.getpid()}:{self._pkg_path.name}".encode()).hexdigest()[:12]
        tmp_target = f"/tmp/pkgforge_{unique}_{self._pkg_path.name}"
        q_tmp = shlex.quote(tmp_target)

        if pkg_type == "deb":
            install_cmd = f"sudo dpkg -i {q_tmp} || sudo apt-get install -f -y"
        else:
            install_cmd = f"sudo rpm -i {q_tmp} || sudo dnf install -y {q_tmp}"

        # Copy file into the shared /tmp and install via distrobox enter.
        full_cmd = (
            f"cp {shlex.quote(str(self._pkg_path))} {q_tmp} && "
            f"{shlex.quote(self._tools.distrobox)} enter {shlex.quote(self._container_name)} -- "
            f"bash -c {shlex.quote(install_cmd)}"
        )

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_install_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._process.start("/bin/bash", ["-c", full_cmd])

    def _on_install_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if exit_code != 0:
            self.finished.emit(False, f"Container içi kurulum başarısız (kod: {exit_code})")
            return

        self.output_line.emit("✓ Paket container içinde kuruldu")
        self._phase = "export"
        self._export_app()

    def _export_app(self) -> None:
        """Export the application's desktop entry from container to host."""
        self.output_line.emit("▶ Masaüstü kısayolu dışa aktarılıyor...")

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_export_finished)
        self._process.errorOccurred.connect(self._on_error)

        self._process.start(self._tools.distrobox, [
            "enter", self._container_name, "--",
            "distrobox-export", "--app", self._pkg_name,
        ])

    def _on_export_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if exit_code != 0:
            # Export failure is not critical
            self.output_line.emit("⚠ Masaüstü kısayolu dışa aktarılamadı (manuel: distrobox-export --app)")
            self.finished.emit(True, f"{self._pkg_name} container'da kuruldu (kısayol manuel)")
        else:
            self.output_line.emit("✓ Masaüstü kısayolu oluşturuldu")
            self.finished.emit(True, f"{self._pkg_name} container'da kuruldu ve sisteme entegre edildi")

    def _on_output(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            stripped = line.strip()
            if stripped:
                self.output_line.emit(f"  {stripped}")

    def _on_error(self, error: QProcess.ProcessError) -> None:
        self.finished.emit(False, f"Distrobox hatası ({self._phase}): {error}")
