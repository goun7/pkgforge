"""PkgForge — DEB Converter Plugin.

Wraps the existing NativeDebConverter as a plugin for the plugin system.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from config import ToolPaths
from core.plugins import ConverterPlugin

log = logging.getLogger(__name__)


class DebConverterPlugin(ConverterPlugin):
    """DEB package converter plugin."""

    name = "deb"
    extensions = (".deb",)
    priority = 10  # High priority — this is the primary converter
    category = "converter"
    description = "Native DEB to Arch Linux converter"
    author = "PkgForge"
    version = "1.1.0"

    def is_available(self, tools: ToolPaths) -> bool:
        """Check if DEB conversion tools are available."""
        return bool(tools.makepkg and tools.bsdtar)

    def convert(
        self,
        input_path: Path,
        output_dir: Path,
        tools: ToolPaths,
        **kwargs: Any,
    ) -> tuple[bool, str, Path | None]:
        """Convert DEB to Arch package.

        Uses NativeDebConverter (subprocess mode) for headless operation.
        Falls back to debtap if native conversion fails.
        """
        try:
            from core.subprocess_converters import NativeDebConverterSubprocess

            converter = NativeDebConverterSubprocess(tools)
            result: dict[str, Any] = {}

            def on_done(success: bool, msg: str, pkg: Any) -> None:
                result["success"] = success
                result["message"] = msg
                result["output_pkg"] = pkg

            converter.finished.connect(on_done)

            import threading
            done_event = threading.Event()

            def on_done_with_event(success: bool, msg: str, pkg: Any) -> None:
                result["success"] = success
                result["message"] = msg
                result["output_pkg"] = pkg
                done_event.set()

            # Reconnect with event
            try:
                converter.finished.disconnect(on_done)
            except (TypeError, RuntimeError):
                pass
            converter.finished.connect(on_done_with_event)

            converter.convert(input_path, output_dir)
            done_event.wait(timeout=120)

            return (
                result.get("success", False),
                result.get("message", "Dönüşüm tamamlanamadı"),
                result.get("output_pkg"),
            )

        except ImportError:
            return False, "Subprocess converter mevcut değil", None
        except Exception as exc:  # noqa: BLE001
            log.warning("DEB plugin dönüşüm hatası: %s", exc)
            return False, f"Dönüşüm hatası: {exc}", None
