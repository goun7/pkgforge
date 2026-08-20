"""PkgForge — DEB to RPM Converter Plugin.

Converts .deb packages to .rpm format using alien.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from config import ToolPaths
from core.plugins import ConverterPlugin
from core.security import safe_run

log = logging.getLogger(__name__)


class DebToRpmConverter(ConverterPlugin):
    """Convert .deb packages to .rpm using alien."""

    name = "deb-to-rpm"
    extensions = [".deb"]
    priority = 200  # Lower priority than native DEB converter (100)

    def is_available(self, tools: ToolPaths) -> bool:
        """Check if alien is available."""
        return bool(shutil.which("alien"))

    def convert(
        self,
        input_path: Path,
        output_dir: Path,
        tools: ToolPaths,
        **kwargs: Any,
    ) -> tuple[bool, str, Path | None]:
        """Convert a .deb package to .rpm.

        Args:
            input_path: Path to the .deb file.
            output_dir: Directory to write the .rpm file.
            tools: Detected system tools.

        Returns:
            (success, message, output_path)
        """
        alien = shutil.which("alien")
        if not alien:
            return False, "alien bulunamadı — DEB→RPM dönüşümü için gerekli", None

        output_dir.mkdir(parents=True, exist_ok=True)

        res = safe_run(
            [alien, "--to-rpm", "--to-version", "", str(input_path)],
            cwd=str(output_dir),
            timeout=300,
        )

        if res.returncode != 0:
            stderr = res.stderr.decode("utf-8", errors="replace") if isinstance(res.stderr, bytes) else str(res.stderr)
            return False, f"alien başarısız: {stderr[:200]}", None

        # Find the generated .rpm file
        rpm_files = list(output_dir.glob("*.rpm"))
        if not rpm_files:
            return False, "RPM dosyası oluşturulamadı", None

        rpm_path = rpm_files[0]
        log.info("DEB→RPM dönüşümü tamamlandı: %s", rpm_path.name)
        return True, f"Dönüşüm başarılı: {rpm_path.name}", rpm_path
