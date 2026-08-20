# ADR-002: Plugin System for Converters

## Status

Accepted

## Context

PkgForge started with hardcoded DEB and RPM converters. As the project grew to support Flatpak, AppImage, OCI, and potentially other formats, the converter code became scattered across multiple files with duplicated interface patterns. Adding a new format required modifying core pipeline files.

## Decision

Introduce a plugin system in `core/plugins/`:

1. **Base class**: `ConverterPlugin` ABC with `name`, `extensions`, `priority`, `is_available()`, `convert()`
2. **Auto-discovery**: `pkgutil.iter_modules()` scans `core/plugins/` at import time
3. **Priority-based selection**: Lower priority = preferred converter (e.g., native converter at 50, fallback at 100)
4. **Hot-reload**: `reload_plugins()` clears registry and re-imports; SIGHUP handler triggers reload on Unix
5. **Extension routing**: `get_converter_for_file()` selects best plugin by file extension

**Plugin API contract:**
```python
class MyConverter(ConverterPlugin):
    name = "myformat"
    extensions = [".myformat", ".mf"]
    priority = 50

    def is_available(self, tools: ToolPaths) -> bool:
        return True

    def convert(self, input_path, output_dir, tools, **kwargs):
        return True, "Success", output_path
```

## Consequences

- New formats can be added by dropping a file in `core/plugins/` — no core changes
- Existing DEB/RPM converters can be refactored into plugins without breaking the pipeline
- Hot-reload enables development iteration without restarting the GUI
- Priority system allows graceful fallback (e.g., native → debtap → docker)
