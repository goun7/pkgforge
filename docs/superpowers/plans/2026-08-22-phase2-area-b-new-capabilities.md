# Faz 2 — Alan B: Yeni Yetenekler Implementation Plan

> **For agentic workers:** Execute inline milestone-by-milestone with TDD + frequent commits.

**Spec:** docs/superpowers/specs/2026-08-22-phase2-area-b-new-capabilities-design.md
**Roadmap:** docs/ROADMAP.md (B1–B8, BINDING)

## Conventions (Phase 0/1 — follow exactly)
- Python tests: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ --timeout=180 -p no:cacheprovider`
- Frontend: `cd desktop && pnpm vitest run` / `pnpm build`
- Rust: `cd desktop/src-tauri && cargo build`
- Lint: ruff + mypy on touched python; tsc clean on touched TS
- Sidecar test pattern: tests/test_api_server.py subprocess fixture
- Commit after each milestone. Repo PRIVATE.

## Milestones

### F2.1 — B8 Plugins + B5 Compare (hazır kod wiring)
1. tests/test_api_server_phase2.py: plugin.list/available/install/uninstall/update/audit + compare.diff tests (fail first)
2. api_server.py: plugin.* handlers (core.plugins.marketplace) + compare.diff (generate_sbom + diff_sboms)
3. Frontend: Plugins.tsx + Compare.tsx + tests; sidebar activate plugins, add compare
4. Commit

### F2.2 — B1 AUR Browse
1. core/aur_checker.py: add search_aur(query, limit) using /rpc/v5/search (new code, tested offline)
2. api_server.py: aur.search/info/build handlers (build = clone + makepkg, threaded, event.aur_build_*)
3. Frontend: Browse.tsx + test; sidebar activate browse
4. Commit

### F2.3 — B4 CVE
1. core/cve_scanner.py: NEW — scan_dependencies(deps) via OSV.dev; offline graceful
2. tests/test_cve_scanner.py (mock urllib)
3. api_server.py: security.cve_scan handler
4. Frontend: Security.tsx CVE tab + test
5. Commit

### F2.4 — B3 Scheduler + B6 Toplu işlem
1. api_server.py: schedule.get/set + scheduler daemon thread (event.schedule_ran)
2. api_server.py: queue.* handlers; _pipelines dict keyed by item id; events carry item_id
3. Frontend: Updates scheduler card; Convert queue priority/filter/bulk
4. Commit

### F2.5 — B2 Tray + Bildirim (Rust)
1. Cargo.toml: tauri-plugin-notification; lib.rs: tray icon + menu, notification on event.finished
2. cargo build clean; E2E app boot
3. Commit

### F2.6 — B7 Web/LAN
1. core/api_server.py: serve_http(port, token) — http.server JSON-RPC, bearer auth
2. main.py: serve --http/--port/--token flags
3. tests: http roundtrip with token (localhost)
4. Commit

### F2.7 — Entegrasyon + ROADMAP + push
1. Full suites (python + vitest + cargo + ruff/mypy + tsc)
2. E2E integration script
3. ROADMAP B1–B8 ✅
4. Commit + push

## Definition of Done (per milestone)
- Tests first (red), then green; regression suite green before commit.
- ruff/mypy/tsc clean on touched files.
- Commit message references milestone + roadmap item.
