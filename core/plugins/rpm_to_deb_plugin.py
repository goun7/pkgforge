"""PkgForge — RPM to DEB Converter Plugin.

Converts .rpm packages to .deb format using alien.
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


class RpmToDebConverter(ConverterPlugin):
    """Convert .rpm packages to .deb using alien."""

    name = "rpm-to-deb"
    extensions = (".rpm",)
    priority = 200  # Lower priority than native RPM converter (100)
    category = "converter"
    description = "RPM to DEB converter using alien"
    author = "PkgForge"
    version = "1.0.0"

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
        """Convert an .rpm package to .deb.

        Args:
            input_path: Path to the .rpm file.
            output_dir: Directory to write the .deb file.
            tools: Detected system tools.

        Returns:
            (success, message, output_path)
        """
        alien = shutil.which("alien")
        if not alien:
            return False, "alien bulunamadı — RPM→DEB dönüşümü için gerekli", None

        output_dir.mkdir(parents=True, exist_ok=True)

        res = safe_run(
            [alien, "--to-deb", str(input_path)],
            cwd=str(output_dir),
            timeout=300,
        )

        if res.returncode != 0:
            stderr = res.stderr.decode("utf-8", errors="replace") if isinstance(res.stderr, bytes) else str(res.stderr)
            return False, f"alien başarısız: {stderr[:200]}", None

        # Find the generated .deb file
        deb_files = list(output_dir.glob("*.deb"))
        if not deb_files:
            return False, "DEB dosyası oluşturulamadı", None

        deb_path = deb_files[0]
        log.info("RPM→DEB dönüşümü tamamlandı: %s", deb_path.name)
        return True, f"Dönüşüm başarılı: {deb_path.name}", deb_path
