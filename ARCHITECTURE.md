# PkgForge Architecture

## Overview

PkgForge is a modular Python application with a clear separation between CLI, GUI, and core logic.

```
┌─────────────────────────────────────────────────────┐
│                    main.py                          │
│              (Entry Point + Dispatch)               │
└──────────┬──────────────────────┬───────────────────┘
           │                      │
    ┌──────▼──────┐        ┌──────▼──────┐
    │   cli.py    │        │  ui/main    │
    │  (CLI)      │        │  (GUI)      │
    └──────┬──────┘        └──────┬──────┘
           │                      │
    ┌──────▼──────────────────────▼──────┐
    │           core/ (Business Logic)    │
    │  ┌─────────┐  ┌──────────┐         │
    │  │ security│  │ pipeline │  ...     │
    │  └─────────┘  └──────────┘         │
    └────────────────────────────────────┘
```

## Core Modules

### Security Layer (`core/security.py`)
- `safe_run()` — All subprocess calls go through here
- Shell=False enforcement, timeout, logging
- Path traversal detection, MIME validation, SHA-256 hashing

### Conversion Pipeline (`core/pipeline.py`)
- `ConversionPipeline` — Orchestrates the full convert flow
- Signal-based progress reporting (works with both CLI and GUI)
- Step-by-step: security → analysis → compatibility → conversion → quality

### Plugin System (`core/plugins/`)
- `ConverterPlugin` ABC — Base class for all converters
- Hot-reload via SIGHUP
- Marketplace for community plugins

### Data Layer
- `core/history_db.py` — SQLite with WAL mode for conversion history
- `core/offline_cache.py` — File-based cache for network operations
- `core/snapshot_manager.py` — Btrfs/ZFS snapshot management

## Key Design Decisions

See [docs/adr/](docs/adr/) for detailed ADRs:
- **ADR-001**: WAL mode for SQLite concurrent access
- **ADR-002**: Plugin system with ABC base class
- **ADR-003**: CLI/GUI split with shared core

## Security Model

1. **No shell=True** — All subprocess calls use `safe_run()` with shell=False
2. **Input validation** — Package names validated before use
3. **Sandbox isolation** — Bubblewrap sandbox for build operations
4. **Timeout enforcement** — All operations have timeouts
5. **Logging** — All errors logged, never silently swallowed

## Testing Strategy

- **Unit tests** — Individual function testing
- **Integration tests** — CLI command testing
- **E2E tests** — Real package conversion testing
- **Property-based tests** — Hypothesis for edge cases
- **Security tests** — Injection, traversal, bomb detection
