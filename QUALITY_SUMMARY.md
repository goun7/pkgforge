# PkgForge Quality Gates Summary

Measured 2026-09-07 via `make verify` (single source of truth; thresholds
in `pyproject.toml`):

- ✅ Ruff 0.16.4: 0 errors (full repo, CI-parity)
- ✅ Mypy: 0 errors / 95 source files (`core/`+`cli.py`+`main.py`+`config.py`)
- ✅ Bandit: No issues (`-ll`, core + entry points)
- ✅ Pytest: 2576 tests — 2572 passed, 4 skipped, 0 failed
  (systemd/pkexec-dependent, fail on clean tree too)
- ✅ Coverage: 99% (12 806 statements, 47 missed; gate `--cov-fail-under=99`)
- ✅ i18n: 987/987 tr/en parity, `--lang en` smoke-tested
- ✅ pip-audit: clean; CI `supply-chain` job added
- ✅ Desktop: Tauri strict CSP (was `null`), vitest suite green in CI

Historical session logs: `progress.md`, `task_plan.md`, `findings.md`.
Authoritative release state: `/RELEASE_READINESS.md`.
