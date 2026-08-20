# Contributing to PkgForge

Thank you for your interest in contributing to PkgForge! This document provides guidelines and information for contributors.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/pkgforge/pkgforge.git
cd pkgforge

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-timeout hypothesis mypy bandit

# Run tests
python -m pytest tests/ -m "not slow"

# Type check
mypy core/ --ignore-missing-imports

# Run benchmarks
python main.py benchmark --quick
```

## Code Style

- **Python 3.10+** — use type hints everywhere
- **Black** formatting (or match existing style)
- **Docstrings** — all public functions must have docstrings
- **Logging** — use `log.debug()` for error handling, never `except: pass`
- **safe_run** — all subprocess calls must use `safe_run()` from `core/security.py`

## Testing

- Write tests for all new features
- Use `@pytest.mark.slow` for tests > 5 seconds
- Property-based testing with Hypothesis for core functions
- Mock network calls in tests

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Run the full test suite: `python -m pytest tests/ -m "not slow"`
4. Run type check: `mypy core/ --ignore-missing-imports`
5. Update CHANGELOG.md if applicable
6. Submit PR with clear description

## Plugin Development

To create a new converter plugin:

```python
from core.plugins import ConverterPlugin

class MyConverter(ConverterPlugin):
    name = "myformat"
    extensions = [".myformat"]
    priority = 50
    category = "converter"
    description = "My custom converter"
    author = "Your Name"
    version = "1.0.0"

    def is_available(self, tools):
        return True

    def convert(self, input_path, output_dir, tools, **kwargs):
        return True, "Success", output_path
```

Place the plugin file in `core/plugins/` or install it via marketplace.

## Architecture

See [docs/adr/](docs/adr/) for architectural decision records.

## License

By contributing, you agree that your contributions will be licensed under GPL-3.0-or-later.
