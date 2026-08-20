# ADR-003: PyQt6-Free CLI Path

## Status

Accepted

## Context

PkgForge has two interfaces: a PyQt6 GUI and a headless CLI. Early versions imported PyQt6 at module level in pipeline.py and converter modules, causing `ImportError` on headless servers or systems without PyQt6 installed. This prevented using the CLI on minimal Arch installations.

## Decision

Maintain a strict separation between GUI and CLI code paths:

1. **`core/subprocess_converters.py`**: Drop-in replacements for `NativeDebConverter` and `RpmConverter` that use `subprocess.Popen` instead of `QThread` signals
2. **`core/cli_bridge.py`**: Synchronous conversion functions (`convert_deb_sync`, `convert_rpm_sync`) for CLI use
3. **Conditional imports in `pipeline.py`**: `TYPE_CHECKING` block for mypy, runtime `try/except ImportError` with minimal stubs
4. **Test gate**: CI verifies all 30+ core modules import without PyQt6 (`Module Import Check` step)

**Import chain:**
```
CLI path:  main.py → cli.py → cli_bridge.py → subprocess_converters.py (no Qt)
GUI path:  main.py → ui/main_window.py → pipeline.py → native_deb_converter.py (uses Qt)
```

## Consequences

- `pip install pkgforge` works without PyQt6 for CLI-only usage
- `pip install pkgforge[gui]` adds PyQt6 for the full GUI
- All core security, analysis, and conversion logic is testable without a display server
- Pipeline.py uses `TYPE_CHECKING` to satisfy mypy while maintaining runtime flexibility
