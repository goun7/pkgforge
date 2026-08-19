"""PkgForge — Plugin System for Converters.

Enables adding new package format converters by dropping Python files
in this directory. Each plugin must define a ConverterPlugin class.

Usage:
    from core.plugins import load_plugins, get_converter

    plugins = load_plugins()
    converter = get_converter("deb")  # Returns NativeDebConverter or plugin
    ok, msg, path = converter.convert(input_path, output_dir, tools)
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from config import ToolPaths

log = logging.getLogger(__name__)

# Registry of converter plugins
_REGISTRY: dict[str, type] = {}


class ConverterPlugin(ABC):
    """Base class for converter plugins.

    To create a new converter, create a file in core/plugins/ with:
        class MyConverter(ConverterPlugin):
            name = "myformat"
            extensions = [".myformat", ".mf"]
            priority = 50  # Lower = preferred (default converters use 100)

            def is_available(self, tools: ToolPaths) -> bool:
                return True

            def convert(self, input_path: Path, output_dir: Path,
                       tools: ToolPaths, **kwargs) -> tuple[bool, str, Path | None]:
                return True, "Converted", output_path
    """

    name: str = ""              # Converter identifier (e.g., "deb", "rpm")
    extensions: list[str] = []  # File extensions this converter handles
    priority: int = 100         # Lower priority = preferred converter

    @abstractmethod
    def is_available(self, tools: ToolPaths) -> bool:
        """Check if this converter's dependencies are available."""

    @abstractmethod
    def convert(
        self,
        input_path: Path,
        output_dir: Path,
        tools: ToolPaths,
        **kwargs: Any,
    ) -> tuple[bool, str, Path | None]:
        """Convert a package file.

        Args:
            input_path: Path to the input package file.
            output_dir: Directory to write the output.
            tools: Detected system tools.
            **kwargs: Additional converter-specific options.

        Returns:
            (success, message, output_path)
        """
        ...


def register_plugin(plugin_class: type) -> None:
    """Register a converter plugin class."""
    if not issubclass(plugin_class, ConverterPlugin):
        raise TypeError(f"Plugin must subclass ConverterPlugin, got {plugin_class}")
    instance = plugin_class()
    if instance.name:
        _REGISTRY[instance.name] = plugin_class
        log.debug("Plugin registered: %s (%s)", instance.name, plugin_class.__name__)


def load_plugins() -> dict[str, ConverterPlugin]:
    """Load all plugins from core/plugins/ directory.

    Returns:
        Dict of name -> plugin instance.
    """
    plugins_dir = Path(__file__).parent
    loaded: dict[str, ConverterPlugin] = {}

    for finder, module_name, is_pkg in pkgutil.iter_modules([str(plugins_dir)]):
        if is_pkg or module_name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"core.plugins.{module_name}")
            # Find classes that subclass ConverterPlugin
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type)
                    and issubclass(attr, ConverterPlugin)
                    and attr is not ConverterPlugin):
                    instance = attr()
                    if instance.name:
                        _REGISTRY[instance.name] = attr
                        loaded[instance.name] = instance
                        log.info("Loaded plugin: %s from %s", instance.name, module_name)
        except Exception as exc:
            log.warning("Failed to load plugin %s: %s", module_name, exc)

    return loaded


def get_converter_for_file(file_path: Path) -> ConverterPlugin | None:
    """Find the best converter for a given file extension.

    Args:
        file_path: Path to the package file.

    Returns:
        Best matching ConverterPlugin, or None if no plugin handles this extension.
    """
    suffix = file_path.suffix.lower()

    # Check if any plugin handles this extension
    candidates: list[tuple[int, ConverterPlugin]] = []
    for name, plugin_cls in _REGISTRY.items():
        plugin = plugin_cls()
        if suffix in plugin.extensions:
            candidates.append((plugin.priority, plugin))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    return None


def get_converter(name: str) -> ConverterPlugin | None:
    """Get a converter plugin by name.

    Args:
        name: Converter name (e.g., "deb", "rpm", "flatpak").

    Returns:
        ConverterPlugin instance, or None.
    """
    plugin_cls = _REGISTRY.get(name)
    if plugin_cls:
        return plugin_cls()
    return None


def list_plugins() -> list[dict[str, Any]]:
    """List all registered plugins.

    Returns:
        List of dicts with name, extensions, priority, available status.
    """
    result = []
    for name, plugin_cls in sorted(_REGISTRY.items()):
        plugin = plugin_cls()
        result.append({
            "name": plugin.name,
            "extensions": plugin.extensions,
            "priority": plugin.priority,
            "class": plugin_cls.__name__,
        })
    return result


# Auto-load plugins on import
load_plugins()
