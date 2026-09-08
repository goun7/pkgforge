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
import importlib.util
import logging
import pkgutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from config import ToolPaths

log = logging.getLogger(__name__)

# Registry of converter plugins
_REGISTRY: dict[str, type[ConverterPlugin]] = {}


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

    name: str = ""                # Converter identifier (e.g., "deb", "rpm")
    extensions: tuple[str, ...] = ()  # File extensions this converter handles
    priority: int = 100           # Lower priority = preferred converter
    category: str = "converter" # Plugin category: converter, security, analyzer, utility
    description: str = ""       # Short description of the plugin
    author: str = ""            # Plugin author
    version: str = "1.0.0"      # Plugin version

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
    """Load all plugins from core/plugins/ and marketplace directory.

    Returns:
        Dict of name -> plugin instance.
    """
    loaded: dict[str, ConverterPlugin] = {}
    _loaded_modules: set[str] = set()

    # 1. Load built-in plugins from core/plugins/
    plugins_dir = Path(__file__).parent
    for finder, module_name, is_pkg in pkgutil.iter_modules([str(plugins_dir)]):
        if is_pkg or module_name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"core.plugins.{module_name}")
            _loaded_modules.add(module_name)
            _register_module(module, loaded)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to load plugin %s: %s", module_name, exc)

    # 2. Load marketplace plugins from ~/.config/pkgforge/plugins/
    try:
        from core.plugins.marketplace import PLUGIN_DIR
        if PLUGIN_DIR.exists():
            for py_file in PLUGIN_DIR.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                mod_name = f"_marketplace_{py_file.stem}"
                if mod_name in _loaded_modules:  # pragma: no cover — küme her çağrıda taze
                    continue
                try:
                    spec = importlib.util.spec_from_file_location(mod_name, py_file)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        _loaded_modules.add(mod_name)
                        _register_module(module, loaded)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Failed to load marketplace plugin %s: %s", py_file.name, exc)
    except ImportError:
        pass

    return loaded


def _register_module(module: object, loaded: dict[str, ConverterPlugin]) -> None:
    """Register ConverterPlugin subclasses from a module."""
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (isinstance(attr, type)
            and issubclass(attr, ConverterPlugin)
            and attr is not ConverterPlugin):
            instance = attr()
            if instance.name:
                _REGISTRY[instance.name] = attr
                loaded[instance.name] = instance
                log.info("Loaded plugin: %s", instance.name)


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
    for plugin_cls in _REGISTRY.values():
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


def list_plugins(category: str | None = None) -> list[dict[str, Any]]:
    """List all registered plugins.

    Args:
        category: Optional filter by category (converter, security, analyzer, utility).

    Returns:
        List of dicts with name, extensions, priority, category, description, etc.
    """
    result = []
    for name, plugin_cls in sorted(_REGISTRY.items()):
        plugin = plugin_cls()
        if category and plugin.category != category:
            continue
        result.append({
            "name": plugin.name,
            "extensions": plugin.extensions,
            "priority": plugin.priority,
            "category": plugin.category,
            "description": plugin.description,
            "author": plugin.author,
            "version": plugin.version,
            "class": plugin_cls.__name__,
        })
    return result


def reload_plugins() -> dict[str, ConverterPlugin]:
    """Reload all plugins, replacing any previously loaded ones.

    Clears the registry and re-imports all plugin modules.
    Useful for hot-reloading during development or via SIGHUP.

    Returns:
        Dict of name -> plugin instance after reload.
    """
    # No 'global' needed: we mutate the dict in place, not rebind the name.
    _REGISTRY.clear()
    log.info("Plugin registry cleared, reloading...")
    return load_plugins()


def _setup_sighup_handler() -> None:
    """Install SIGHUP handler for plugin hot-reload (Unix only)."""
    import signal
    import sys

    if sys.platform == "win32":
        return  # SIGHUP not available on Windows

    def _handle_sighup(signum: int, frame: object) -> None:
        log.info("SIGHUP received — reloading plugins")
        try:
            reloaded = reload_plugins()
            log.info("Plugins reloaded: %d plugins active", len(reloaded))
        except Exception as exc:  # noqa: BLE001
            log.error("Plugin reload failed: %s", exc)

    try:
        signal.signal(signal.SIGHUP, _handle_sighup)
        log.debug("SIGHUP handler installed for plugin hot-reload")
    except (OSError, ValueError):
        pass  # Not in main thread or signal not available


# Auto-load plugins on import
load_plugins()
_setup_sighup_handler()