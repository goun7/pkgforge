# Changelog

All notable changes to PkgForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

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

#### Testing & CI
- E2E tests with real RPM packages
- GitHub Actions CI pipeline with benchmark gate (30s threshold)
- 60+ unit and integration tests

#### New Commands (v1.1)
- **`pkgforge quality`** — Package quality scoring (A-F grade, 100-point scale)
- **`pkgforge publish`** — AUR auto-publish (PKGBUILD + .SRCINFO + git push)
- **`pkgforge verify-rollback`** — Automated snapshot rollback verification
- **`pkgforge health`** — Health dashboard with success rates and error patterns
- **`pkgforge abi-check`** — GLIBC/GLIBCXX symbol version mismatch detection
- **`pkgforge snapshot-cleanup`** — Systemd timer for automatic snapshot cleanup
- **`convert --resolve-deps`** — Auto-resolve missing dependencies (pacman + AUR)
- **`convert --offline`** — Offline mode with local cache
- **`--clear-cache`** — Purge all cached data

#### Architecture (v1.1)
- Plugin system for converters (`core/plugins/`)
- Smart fallback chain: native → debtap → docker → distrobox
- Offline cache with TTL and atomic writes
- Retry with exponential backoff for HTTP/AUR operations
- Thread-safe pipeline (threading.Lock)
- All 26 core modules import without PyQt6

## [1.0.0] — Initial Release

### Features
- DEB → Arch Linux conversion (debtap + native)
- RPM → Arch Linux conversion (debtap + rpm2cpio)
- PyQt6 GUI with drag-and-drop
- CLI interface with `convert`, `list`, `remove`, `rollback`
- Package compatibility analysis (namcap, ldd, dependency resolution)
- Browser warning dialog for Distrobox fallback
- 13-layer security validation
- Multi-language support (Turkish/English)
- Dark/Light/System theme support
