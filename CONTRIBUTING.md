# Contributing to PkgForge

Thank you for your interest in contributing to PkgForge! This document provides guidelines for contributing.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/user/pkgforge.git
cd pkgforge

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Run type checks
python -m py_compile main.py cli.py
```

## Project Structure

```
pkgforge/
├── main.py                 # Application entry point + CLI arg parser
├── cli.py                  # Headless CLI handlers (no Qt dependency)
├── config.py               # Configuration, tool discovery, temp dirs
├── core/                   # Core conversion & analysis engine
│   ├── pipeline.py         # Main conversion pipeline (GUI-side)
│   ├── cli_bridge.py       # CLI bridge (threading-based, no Qt event loop)
│   ├── subprocess_converters.py  # Subprocess-based converters for CLI
│   ├── package_analyzer.py # Package metadata extraction
│   ├── compatibility_checker.py  # Arch compatibility analysis
│   ├── security.py         # Security checks (MIME, SHA, traversal, bombs)
│   ├── malware_scanner.py  # ClamAV integration
│   ├── provenance.py       # SLSA provenance tracking
│   ├── package_signing.py  # GPG signing & verification
│   ├── dep_graph.py        # Dependency graph visualization
│   ├── benchmark.py        # Performance benchmarks
│   ├── snapshot_manager.py # Btrfs/ZFS snapshot management
│   ├── delta_updater.py    # Binary differential updates (xdelta3)
│   ├── oci_builder.py      # OCI container image builder
│   ├── reproducible_build.py  # Reproducible build verification
│   ├── rpm_to_deb_converter.py # RPM → DEB conversion
│   ├── flatpak_converter.py    # Flatpak → DEB conversion
│   ├── appimage_converter.py   # AppImage → DEB conversion
│   ├── history_db.py       # SQLite history & backup management
│   ├── upstream_tracker.py # Upstream update detection
│   ├── native_deb_converter.py  # Native DEB → Arch converter
│   └── rpm_converter.py    # Native RPM → Arch converter
├── i18n/                   # Internationalization
│   ├── lang_tr.py          # Turkish strings
│   └── lang_en.py          # English strings
├── ui/                     # PyQt6 GUI (optional)
├── tests/                  # Test suite
├── data/                   # Static data files
└── scripts/                # Helper scripts
```

## Adding a New Converter

1. Create `core/your_converter.py` with:
   ```python
   def is_available() -> bool:
       """Check if conversion tools are installed."""
       
   def convert(input_path: Path, output_dir: Path) -> tuple[bool, str, Path | None]:
       """Convert package. Returns (success, message, output_path)."""
   ```

2. Add CLI handler in `cli.py`:
   ```python
   def _cmd_your_converter(args: argparse.Namespace) -> int:
       from core.your_converter import convert
       ok, msg, path = convert(...)
       return 0 if ok else 1
   ```

3. Register in `main.py` subparser + `cli.py` routing.

4. Add i18n strings in `i18n/lang_tr.py` and `i18n/lang_en.py`.

5. Write tests in `tests/test_your_converter.py`.

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_security.py -v

# Skip GUI tests (no display)
python -m pytest tests/ --ignore=tests/test_gui.py

# With coverage
python -m pytest tests/ --cov=core --cov-report=term-missing
```

## Code Style

- **Type hints**: Always use them. `from __future__ import annotations` at top.
- **Logging**: Use `logging.getLogger(__name__)`, not `print()`.
- **CLI output**: Use ANSI color constants from `cli.py` (`GREEN`, `RED`, `BOLD`, etc.).
- **i18n**: All user-facing strings go through `tr("key")`.
- **Security**: Never use `shell=True` with user input. Use `safe_run()` from `core/security.py`.
- **No PyQt6 in core/cli**: `core/` and `cli.py` must not import PyQt6. Use `subprocess` instead.

## Commit Messages

Use imperative mood with a scope prefix:

```
fix(security): prevent zip bomb detection bypass
feat(converters): add RPM-to-DEB converter
test(e2e): add real-world RPM analysis tests
docs(readme): update CLI command reference
```

## Security

If you find a security vulnerability, please report it privately via email
rather than opening a public issue. See SECURITY.md for details.
