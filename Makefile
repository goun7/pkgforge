# PkgForge — tek doğruluk kaynağı (Faz 0).
# `make verify` == CI kapıları. Eşikler/kümeler pyproject.toml'da tanımlı.
PY ?= .venv/bin/python

.PHONY: verify lint typecheck security test coverage count

verify: lint typecheck security test

lint:
	$(PY) -m ruff check . 2>/dev/null || ruff check .

typecheck:
	$(PY) -m mypy core/ cli.py main.py config.py ui/ --ignore-missing-imports --strict --no-error-summary

security:
	$(PY) -m bandit -r core/ cli.py main.py config.py -ll --skip B101,B311

test:
	$(PY) -m pytest tests/ -q --cov=core --cov=ui --cov=i18n --cov-report=term --cov-fail-under=99

count:
	$(PY) -m pytest tests/ --collect-only -q 2>/dev/null | tail -1
