# Changelog

All notable changes to PkgForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **tests**: Oturum-2 kapsam taramaları — pipeline %66→%95,
  security %65→%90, i18n %66→%100, retry %67→%98, malware_scanner %67→%96,
  plugins/marketplace %64→%100 (+~100 yeni test); çekirdek kapsaması
  **%76 → %80**, CI gate **72 → 78**, toplam **1479 test**.

- **desktop**: `pnpm test` / `pnpm test:watch` scripts — the 74 vitest tests
  existed but had no package.json entry point.

### Fixed (Kritiksizlik Taraması)
- **`api_server._validate_aur_name`**: regex accepted names starting with
  `-` or `.`, including `..` — a path-traversal seed reaching
  `tempfile.mkdtemp(prefix=f"pkgforge-aur-{name}-")` and the AUR clone URL.
  First character must now be alphanumeric; regression tests added.
- **rate-limiter test**: asserted "still limited" at t=+999s where every hit
  had already left the 60 s sliding window (would pass only by accident).
  Now asserts at exactly one window length (`now + _HTTP_RATE_LIMIT`).
- **main.py**: `getattr(args, "token_file", "")` typing — mypy is back to
  **0 errors across 75 files**.
- **lint**: ruff **31 → 0** across 11 test files (F841/RUF059/C408/RUF012/B023).
- removed stray tracked junk file `https:/github.com/deneme/proje/CMakeLists.txt`.

### Docs
- README / RELEASE_READINESS synced to measured reality: **1383 passed,
  6 skipped**, **76 %** core coverage, CI gate raised **48 → 72**.

### Fixed (Production-Readiness Audit)
- **`quality_score.score_package`**: package name was derived via
  `pkg_path.stem.split(".")[0]`, which mis-parsed dotted versions
  (`lictest-1.0.0-1-any` → `lictest-1`). Now reads the authoritative `pkgname`
  from `.PKGINFO` and falls back to stripping the `.pkg.tar.*` suffix chain +
  version-rel-arch (consistent with `core/dep_graph.py`).
- **`dep_graph.build_file_dep_graph`**: for `.rpm`/`.deb` inputs the root name
  was the full filename stem (`hello-1.0.0-1.x86_64`) because the hyphen-based
  version-rel-arch strip does not match RPM dot-separated arch. Now uses the
  authoritative `config.extract_package_name` (handles deb/rpm/arch naming).
- **Name-misparse sweep**: the same `stem.split(".")[0]` / `stem.split("-")[0]`
  truncation bug existed in four more fallback paths — `sbom.generate_sbom`,
  `aur_publish._extract_pkg_info` (two sites), and `rpm_to_deb_converter.convert`.
  All now delegate to `config.extract_package_name`, so dotted versions
  (`hello-1.0.0-1-any`) and hyphenated names (`my-cool-app-…`) are preserved.
- **`delta_updater.find_local_previous`**: base name was derived via
  `split("-")[0]` (truncating `my-cool-app` → `my`) and matched with a substring
  check, so a search for `my` over-matched unrelated packages. Now compares the
  full clean package name exactly via `config.extract_package_name`.
- **`history_db.get_usage_stats`**: arch was bucketed as `x86_64.pkg.tar`
  because `.stem` leaves the `.pkg.tar` chain glued to the arch segment; the
  suffix chain is now stripped before parsing.
- **`oci_builder.build_oci_image`**: the image tag was derived from the raw
  stem (`pkgforge/hello-1.0.0-1-x86_64.pkg.tar:latest`); now uses
  `config.extract_package_name` (`pkgforge/hello:latest`).

### Test & Coverage Push
- **614 tests** (up from 261), **52% line coverage** on `core/` (up from 41%);
  skips reduced 13 → 2 by pointing E2E discovery at the committed fixtures.
- Hermetic pure-logic suites: streaming, retry/backoff, SBOM diff, from_source
  build-system/license detection, security (name validation, path traversal,
  symlink escape, ELF heuristics, bubblewrap sandbox builder), shell completion,
  structured-log formatters, snapshot-cleanup generators, HistoryDB (SQLite),
  DepGraph rendering/stats/depth, aur_publish, report_export, provenance
  round-trip + tamper detection, marketplace plugin validation, config
  package-name extraction, converter sanitize/escape (command-injection guard),
  plugin registry, abi_scanner/flatpak/downloader/benchmark/quality_score.
- **Real end-to-end conversions** of the hello `.deb` and hello `.rpm` fixtures
  through the Qt-free subprocess converters (`tests/test_subprocess_converters.py`),
  plus `run_compatibility_checks` and `score_package` against the tracked
  `lictest` `.pkg.tar.zst` fixture.
- **CI coverage gate** raised 35 → 48 to lock in the progress.

### Fixed (earlier audit items)
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
