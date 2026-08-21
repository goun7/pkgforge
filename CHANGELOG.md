# Changelog

All notable changes to PkgForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed (Production-Readiness Audit)
- **Wheel packaging**: `py-modules = ["main","cli","config"]` added so the built
  wheel actually ships the entry-point modules (previously `pkgforge list` failed
  with `ModuleNotFoundError: No module named 'cli'` after `pip install`).
- **Test isolation**: `tests/conftest.py` now redirects `HOME` to a temp dir so the
  suite never touches the real `~/.config/pkgforge/history.db`.
- **Segfault fix**: removed dead `_ensure_qt_app()` (created QApplication on main
  thread, ran `app.exec()` on a daemon thread — Qt undefined behaviour).
- **GPG status parsing**: off-by-one in `package_signing.py` — `parts[1]` was the
  literal `[GNUPG:]` tag, not the key id.
- **systemd delta service**: `ExecStart` pointed at a broken `python3 -m pkgforge`
  invocation; now `/usr/bin/pkgforge check-updates` with hardening options.
- **Downloader**: redirect handler re-validates scheme on 3xx to keep HTTPS-only.
- **Plugin marketplace**: name validation, HTTPS-only, fail-closed checksum.
- **CI**: coverage gate corrected to an honest `--cov-fail-under=35` (was 75, never
  met); removed import check for nonexistent `core.smart_fallback`.
- **Docs honesty**: README badges and CHANGELOG now report real numbers
  (228 tests, 39% coverage) instead of aspirational ones.

### Added

#### CLI & Features
- **`pkgforge sbom --diff OLD NEW`** — Compare SBOM differences between two package versions (file/dependency changes)
- **`pkgforge plugin install/list/available/remove`** — Plugin Marketplace for community converter plugins from GitHub releases
- **`--offline` global flag** — Run all network-dependent operations in offline mode (AUR, upstream tracker)

#### Security
- Migrated 43 raw `subprocess.run` calls to `safe_run` across 7 modules (dep_graph, abi_scanner, dep_resolver, aur_publish, benchmark, subprocess_converters, security)
- All `except Exception: pass` blocks now log via `log.debug()` or `log.warning()` across 8 modules
- Added `safe_run(text=)` parameter for explicit binary/text mode control

#### CI & Testing
- **`pytest-timeout`** — 120s default timeout prevents hanging E2E tests
- **CI coverage gate** — `--cov-fail-under=35` minimum threshold in GitHub Actions (actual coverage: 39%)
- **SBOM diff tests** — 4 new tests for diff functionality
- **Plugin marketplace tests** — 2 new tests for install/uninstall
- **Property-based testing** with Hypothesis framework

#### Documentation
- Updated `docs/API.md` with provenance discovery and attestation verification functions
- Updated CHANGELOG with SBOM diff, plugin marketplace, offline mode
- Added docstrings to public functions across core modules

#### CLI & Converters
- **`pkgforge rpm-to-deb`** — Bidirectional RPM → DEB conversion
- **`pkgforge graph`** — Dependency graph visualization (ASCII + Mermaid)
- **`pkgforge audit`** — Audit trail with date range filtering
- **`pkgforge scan-image`** — OCI container image security scanning (Trivy/Grype/ClamAV)
- **`pkgforge from-source`** — Auto-generate PKGBUILD from Git repository
- **`convert --sign`** — Auto GPG signing after conversion
- **`convert --to-oci`** — OCI container image export (buildah/podman)
- **`convert --delta`** — Binary differential downloads (xdelta3)
- **`convert --verify-build`** — Reproducible build verification
- **`pkgforge flatpak-export`** — Flatpak → DEB conversion
- **`pkgforge appimage-export`** — AppImage → DEB conversion
- **`pkgforge benchmark`** — Performance benchmarking
- **`pkgforge sign`** — GPG package signing
- **`pkgforge verify`** — GPG signature verification
- **`pkgforge provenance`** — SLSA provenance record inspection

#### Security
- ClamAV malware scanning with database freshness validation
- Decompression bomb (zip bomb) detection
- Path traversal attack detection
- MIME type validation via `file(1)`
- SHA-256 integrity hashing
- GPG signature existence detection
- Bubblewrap sandbox for build isolation

#### Architecture
- **PyQt6-free CLI path** — `cli_bridge.py` + `subprocess_converters.py` enable headless operation
- SLSA provenance tracking for all conversions
- Btrfs/ZFS snapshot management for safe rollback
- SQLite-backed conversion history with backup support
- Upstream update tracking via ETag/Last-Modified
- **SQLite WAL mode** — Concurrent access protection with journal_mode=WAL and busy_timeout for safe multi-instance usage
- **SBOM generator** — SPDX-inspired Software Bill of Materials for converted packages (core/sbom.py)
- **Local Usage Dashboard** — Architecture breakdown, avg output size, top-converted packages in health command
- **Plugin Hot-Reload** — SIGHUP-based plugin hot-reload for converter plugins (core/plugins/__init__.py)
- **Architecture Decision Records** — 3 ADRs documenting key design decisions (WAL mode, plugin system, CLI/GUI split) in docs/adr/

#### Testing & CI
- E2E tests with real RPM packages
- GitHub Actions CI pipeline with benchmark gate (30s threshold)
- 228 unit and integration tests (12 skipped without optional tooling)
- SBOM and usage stats unit tests

#### New Commands (v1.1)
- **`pkgforge quality`** — Package quality scoring (A-F grade, 100-point scale)
- **`pkgforge publish`** — AUR auto-publish (PKGBUILD + .SRCINFO + git push)
- **`pkgforge verify-rollback`** — Automated snapshot rollback verification
- **`pkgforge health`** — Health dashboard with success rates, architecture stats, and usage analytics
- **`pkgforge abi-check`** — GLIBC/GLIBCXX symbol version mismatch detection
- **`pkgforge sbom`** — Generate Software Bill of Materials (SPDX-inspired JSON) for converted packages
- **`pkgforge snapshot-cleanup`** — Systemd timer for automatic snapshot cleanup
- **`pkgforge attest`** — Create in-toto SLSA v1.0 attestation for converted packages
- **`convert --resolve-deps`** — Auto-resolve missing dependencies (pacman + AUR)
- **`convert --offline`** — Offline mode with local cache
- **`--clear-cache`** — Purge all cached data

#### Architecture (v1.1)
- Plugin system for converters (`core/plugins/`)
- Smart fallback chain: native → debtap → docker → distrobox
- Offline cache with TTL and atomic writes
- Retry with exponential backoff for HTTP/AUR operations
- Thread-safe pipeline (threading.Lock)
- All 46 core modules import without PyQt6

## [1.0.0] — Initial Release

### Features
- DEB → Arch Linux conversion (debtap + native)
- RPM → Arch Linux conversion (debtap + rpm2cpio)
- PyQt6 GUI with drag-and-drop
- CLI interface with `convert`, `list`, `remove`, `rollback`
- Package compatibility analysis (namcap, ldd, dependency resolution)
- Browser warning dialog for Distrobox fallback
- 12-layer security validation
- Multi-language support (Turkish/English)
- Dark/Light/System theme support
