# Faz 3 — Alan C: Mimari Genişleme Implementation Plan

> **For agentic workers:** Execute inline milestone-by-milestone with TDD + frequent commits.

**Spec:** docs/superpowers/specs/2026-08-22-phase3-area-c-architecture-design.md
**Roadmap:** docs/ROADMAP.md (C1–C3, BINDING)

## Conventions (Phase 0/1/2 — follow exactly)
- Python tests: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ --timeout=180 -p no:cacheprovider`
- Frontend: `cd desktop && pnpm vitest run` / `pnpm build`
- Rust: `cd desktop/src-tauri && cargo build`
- Lint: ruff + mypy on touched python; tsc clean on touched TS
- Sidecar test pattern: tests/test_api_server.py subprocess fixture
- Commit after each milestone. Repo PRIVATE.
- **No new hard deps:** jeepney/WebDAV optional, graceful degradation.

## Milestones

### F3.1 — C2 Çoklu profil
1. core/profiles.py: NEW — list/create/switch/delete/current; profiles/<name>/ layout
2. tests/test_profiles.py (tmp HOME)
3. api_server.py: profile.* handlers; rebind settings/history path on switch
4. Frontend: Settings profile card + test
5. Commit

### F3.2 — C3 Yedekleme/Senkron
1. core/cloud_sync.py: NEW — export_backup/import_backup (zip), webdav_push/pull (urllib)
2. tests/test_cloud_sync.py (zip roundtrip; webdav mocked)
3. api_server.py: sync.* handlers
4. Frontend: Settings backup/sync card + test
5. Commit

### F3.3 — C1 D-Bus
1. core/dbus_service.py: NEW — jeepney session bus service exposing METHODS
2. tests/test_dbus_service.py (skip if jeepney/bus unavailable)
3. api_server.py: dbus.status/start handlers
4. Frontend: Settings D-Bus status card + test
5. Commit

### F3.4 — Entegrasyon + ROADMAP + push
1. Full suites (python + vitest + cargo + ruff/mypy + tsc)
2. E2E integration script
3. ROADMAP C1–C3 ✅
4. Commit + push

## Definition of Done (per milestone)
- Tests first (red), then green; regression suite green before commit.
- ruff/mypy/tsc clean on touched files.
- Commit message references milestone + roadmap item.
