# Faz 1 — Alan A: GUI Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (or execute inline milestone-by-milestone with TDD + frequent commits).

**Spec:** docs/superpowers/specs/2026-08-22-phase1-area-a-gui-wiring-design.md
**Roadmap:** docs/ROADMAP.md (A1–A6, BINDING)

## Conventions (from Phase 0 — follow exactly)

- Python tests: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ --timeout=180 -p no:cacheprovider`
- Frontend tests: `cd desktop && pnpm vitest run`
- Frontend build: `cd desktop && pnpm build` (tsc -b && vite build)
- Rust build: `cd desktop/src-tauri && cargo build`
- Lint: `.venv/bin/python -m ruff check <file>` and `.venv/bin/python -m mypy <file>`
- Sidecar test pattern: see tests/test_api_server.py (`_rpc`, `sidecar` fixture, `_LineReader`)
- Frontend rpc: `call<T>(method, params)` from `../lib/rpc`; events via `onEvent`
- UI tokens: use `var(--*)` from styles/tokens.css; components in components/ui/
- Commit after each milestone. Repo stays PRIVATE.

## File Structure

### Python (sidecar) — extend ONLY core/api_server.py
- `core/api_server.py` — add ~25 handlers + register in METHODS. No new business logic.
  Long-running ops run on `threading.Thread(daemon=True)` and emit `event.*` via `_event()`.
  Serialization: `dataclasses.asdict(report)` + manually add `passed` properties.
- `tests/test_api_server_phase1.py` — unit tests per handler (mock core fns where heavy).

### Frontend
- `desktop/src/lib/types.ts` — add types: SignatureInfo, SbomDoc, QualityReport, Provenance,
  DepGraphData, DeltaStatus, CrossCheck, HealthStats, BenchReport, SnapshotStatus, RollbackVerify,
  FlatpakApp, ExportResult, SourceResult.
- `desktop/src/components/Sidebar.tsx` — activate security/updates/reports, add export item.
- `desktop/src/App.tsx` — wire 4 new pages + PAGE_TITLES.
- `desktop/src/pages/Security.tsx` — NEW
- `desktop/src/pages/Updates.tsx` — NEW
- `desktop/src/pages/Reports.tsx` — NEW
- `desktop/src/pages/Export.tsx` — NEW
- `desktop/src/components/DepGraph.tsx` — NEW (pure SVG radial graph)
- `desktop/src/pages/Convert.tsx` — extend: OCI export btn, graph viewer, "Kaynaktan" tab.
- Vitest: one test file per new page + DepGraph.

---

## Milestone F1.1 — Sidecar A2 (security) + A4 (delta) handlers

### Task 1.1.1: Write failing tests for security.* + delta.*
Create tests/test_api_server_phase1.py. Reuse the `sidecar` fixture pattern from
test_api_server.py (subprocess `main.py serve`, HOME=tmp_path, QT_QPA_PLATFORM=offscreen,
queue-based _LineReader). Tests:
- security.verify on nonexistent path → error code -32000
- security.keys returns list
- security.sigstore_status returns dict
- delta.status returns dict with systemctl_available key
- delta.enable → requires_privilege true (pkexec deferred)
- delta.disable → requires_privilege true
Run → expect failures (methods not registered → -32601).

### Task 1.1.2: Implement security.* + delta.* handlers in api_server.py
Add handlers (lazy-import core modules inside each handler to keep startup fast):
- handle_security_verify(params): pkg_path → verify_signature → asdict
- handle_security_sign(params): thread → sign_package → event.security_done
- handle_security_keys(params): list_keys()
- handle_security_sbom(params): thread → generate_sbom → to_dict → event.security_done
- handle_security_quality(params): thread → score_package → asdict + passed
- handle_security_provenance(params): find_provenance → load → to_dict or null
- handle_security_provenance_create(params): thread → create_provenance → save → to_dict
- handle_security_sigstore_status(params): get_sigstore_status()
- handle_delta_status/enable/disable: get_auto_update_status / enable/disable wrapped
  with requires_privilege guard (return {ok:false, requires_privilege:true, message}).
Register all in METHODS. Run tests → pass. ruff + mypy clean.

### Task 1.1.3: Commit F1.1
`git add core/api_server.py tests/test_api_server_phase1.py && git commit`

---

## Milestone F1.2 — Sidecar A1 (export) + A3 (graph) + A5 (source) + A6 (system)

### Task 1.2.1: Write failing tests
Append to test_api_server_phase1.py:
- graph.build on nonexistent → -32000
- system.health returns dict with total/success_rate keys
- system.snapshot_status returns dict
- system.verify_rollback returns dict with verified/backend keys
- export.flatpak_list returns list (may be empty)
- source.generate with invalid url → error (thread emits event.source_done ok:false)
Run → failures.

### Task 1.2.2: Implement export.* + graph.* + source.* + system.* handlers
- handle_export_oci: thread → build_oci_image → event.export_done
- handle_export_appimage_to_deb: thread → appimage_to_deb → event.export_done
- handle_export_flatpak_list: list_installed_apps → list of asdict
- handle_export_flatpak_to_deb: thread → flatpak_to_deb → event.export_done
- handle_graph_build: thread → build_dep_graph/build_file_dep_graph →
  {root, nodes:{name:asdict}, stats, mermaid} → event.graph_done
- handle_source_generate: thread → clone+detect+generate_pkgbuild_from_source →
  event.source_done {ok, proj_name, build_system, pkgbuild_path, pkgbuild_content}
- handle_system_health: HistoryDB stats → dict (mirror _cmd_health math)
- handle_system_cross_check: thread → cross_check_package → asdict
- handle_system_snapshot_status/install/remove: get_cleanup_status / install/remove
  (install/remove → requires_privilege guard)
- handle_system_verify_rollback: thread → verify_rollback → asdict
- handle_system_benchmark: thread → run_benchmarks → asdict + passed → event.bench_done
Register all. Run tests → pass. ruff + mypy clean.

### Task 1.2.3: Full python suite regression
Run full pytest → all pass (637 baseline + new). Commit F1.2.

---

## Milestone F1.3 — Frontend Security + Updates pages

### Task 1.3.1: Add types to types.ts
Add all Phase 1 types (SignatureInfo, SbomDoc, QualityReport, Provenance, DeltaStatus,
CrossCheck, etc.). Export.

### Task 1.3.2: Write failing vitest for Security.tsx
Create desktop/src/pages/__tests__/Security.test.tsx. Mock `../lib/rpc` call.
Test: renders tabs, package picker present, verify button calls security.verify.
Run → fail (page missing).

### Task 1.3.3: Implement Security.tsx
Package picker (Tauri dialog via @tauri-apps/plugin-dialog, filter .pkg.tar.zst).
Tabs: İmza | SBOM | Kalite | Provenance | Sigstore. Each tab calls its method,
renders result cards/tables using ui components. Loading skeletons, error toasts.
Run vitest → pass.

### Task 1.3.4: Write failing vitest for Updates.tsx + implement
Updates.test.tsx: renders delta status card, enable/disable buttons, cross-check input.
Updates.tsx: delta.status on mount, enable/disable → requires_privilege toast,
cross_check form → result table (local/AUR/Flatpak + recommendation).
Run → pass.

### Task 1.3.5: Activate in Sidebar + App
Sidebar: remove soon from security/updates; App: add to READY_PAGES, import pages,
add PAGE_TITLES. Run pnpm build (tsc) clean. Commit F1.3.

---

## Milestone F1.4 — Frontend Reports + Export pages

### Task 1.4.1: Write failing vitest for Reports.tsx + implement
Reports.test.tsx: renders health dashboard, benchmark run button, snapshot card,
rollback verify button. Reports.tsx: system.health on mount (success-rate ring via
CSS conic-gradient, type bars, arch list); benchmark run → progress → table;
snapshot status + install/remove (requires_privilege toast); verify_rollback → card.
Run → pass.

### Task 1.4.2: Write failing vitest for Export.tsx + implement
Export.test.tsx: renders 3 cards (AppImage, Flatpak, OCI). Export.tsx: three cards.
AppImage→DEB (file pick + convert + progress via event.export_*). Flatpak→DEB
(flatpak_list table + select + convert). OCI (pkg pick + tag input + build + progress).
Subscribe event.export_progress/log/done. Run → pass.

### Task 1.4.3: Add export to Sidebar + App
Sidebar: add { id:"export", label:"Dışa Aktar", icon:PackageOpen }. PageId += "export".
App: READY_PAGES += export, import Export, PAGE_TITLES.export. pnpm build clean.
Commit F1.4.

---

## Milestone F1.5 — Convert extensions + DepGraph component

### Task 1.5.1: Write failing vitest for DepGraph.tsx + implement
DepGraph.test.tsx: renders SVG, nodes colored by status, root present.
DepGraph.tsx: pure-SVG radial layout. Props: {data: DepGraphData}. Compute radial
positions from root BFS depth. Nodes = circles (installed=green/missing=red/foreign=amber),
edges = lines. Hover tooltip. Basic wheel-zoom + drag-pan. No external libs.
Run → pass.

### Task 1.5.2: Extend Convert.tsx
After successful conversion result area add:
- "OCI olarak dışa aktar" button → export.oci + progress toast
- "Bağımlılık grafiği" button → graph.build → open panel rendering <DepGraph/>
Add "Kaynaktan" tab: URL input → source.generate → show detected build_system +
PKGBUILD preview (mono) → save path. Subscribe event.source_*. Run vitest → pass.

### Task 1.5.3: pnpm build clean. Commit F1.5.

---

## Milestone F1.6 — Integration + packaging + release prep

### Task 1.6.1: Full suites
- pytest full → all pass
- pnpm vitest run → all pass
- pnpm build → clean
- cargo build → clean
- ruff + mypy on api_server.py → clean

### Task 1.6.2: E2E integration
Run desktop/scripts/e2e-integration.sh → all checks pass (app boots, sidecar spawns,
clean shutdown). Verify new methods respond via a quick manual rpc probe if needed.

### Task 1.6.3: Update ROADMAP
Mark A1–A6 rows ✅ in docs/ROADMAP.md. Note Faz 1 complete.

### Task 1.6.4: Commit + tag + push
Commit F1.6. Tag v2.0.0-beta (or next agreed tag). Push origin master --tags.
(If KDE wallet blocks push, report blocker with options; local commits are safe.)

---

## Definition of Done (per milestone)
- Tests written FIRST, seen failing, then passing.
- ruff + mypy clean on touched python; tsc clean on touched TS.
- Full regression suite green before commit.
- Commit message references milestone + roadmap item.
