# Task Plan: PkgForge Production-Ready (Overnight)

## Goal (armed: goal-42f5b203)
User sleeps; by morning: all found bugs fixed, tests green, wheel verified,
docs honest, competitor scoring report written, everything committed.

## Fix Queue (priority order)
- [ ] F1 pyproject packaging: py-modules main/cli/config + data-files (PKG-001)
- [ ] F2 installer.py: resolve install_helper.sh from source tree OR sys.prefix
- [ ] F3 conftest.py: isolate HOME before config import (BUG-001)
- [ ] F4 remove dead _ensure_qt_app + its 2 tests (BUG-002 segfault)
- [ ] F5 subprocess_converters: decode bytes → str (BUG-003)
- [ ] F6 marketplace: name validation + fail-closed checksum + https-only (SEC-001)
- [ ] F7 downloader: redirect scheme re-validation (SEC-002)
- [ ] F8 data/pkgforge-delta.service: fix ExecStart (PKG-004)
- [ ] F9 install.sh/uninstall.sh: polkit policy install, version banner (PKG-005/006)
- [ ] F10 CI: remove core.smart_fallback, realistic cov gate, badge continue-on-error (PKG-003/COV-001)
- [ ] F11 ruff --fix safe autofixes; verify tests still green
- [ ] F12 delete stale build/ + egg-info, rebuild wheel, verify contents
- [ ] F13 new tests: from_source, structured_log, streaming, completion, quality_score,
      dep_graph, abi_scanner parsing, delta_updater, snapshot_cleanup, rollback_verify,
      reproducible_build, queue_manager (Qt), pipeline extras
- [ ] F14 measure coverage → set honest CI gate
- [ ] F15 README/CHANGELOG/PKGBUILD honesty pass (badges, test counts, layers, AUR note)
- [ ] F16 competitor research via curl (AUR RPC + GitHub API)
- [ ] F17 docs/RELEASE_READINESS.md: audit report + scoring + release checklist
- [ ] F18 full test run (with PyQt6) + CLI/GUI smoke + wheel smoke
- [ ] F19 git commit everything

## Rules
- Verify every claim with a command (verification-before-completion)
- Log all results to findings.md / progress.md
