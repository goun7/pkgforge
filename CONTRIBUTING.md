# Contributing to PkgForge

Thank you for your interest in contributing to PkgForge! This document provides guidelines and information for contributors.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/goun7/pkgforge.git
cd pkgforge

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-timeout hypothesis mypy bandit

# Run tests (2026-10-17 ölçümü: 7447 test TOPLANIYOR (7443 passed + 4 skipped); atlananlar opsiyonel
# araç entegrasyonlarıdır. Geçme sayısını öğrenmek için bu komut yeterli
# değildir — tam suiti koşan `make verify` gerekir.)
python -m pytest tests/ -q

# Type check (0 hata hedefi)
mypy core cli.py config.py main.py

# Lint (0 hata hedefi)
ruff check .

# Run benchmarks
python main.py benchmark --quick
```

> **Rakamın kaynağı ve gerçek kapı.** Yukarıdaki **7447** sayısı şu komutla
> yeniden üretilir (tam suiti koşmadan):
> `./.venv/bin/python -m pytest --collect-only -q tests` — `-q` çıktısında
> dosya-başına sayım satırları veriliyor; toplamı:
> `./.venv/bin/python -m pytest --collect-only -q tests 2>/dev/null \| grep -E "^tests/[^ ]+\.py: [0-9]+$" \| awk -F': ' '{s+=$2} END {print s}'`.
> Bu bir **toplama (collection-only)** sayısıdır, "testler geçti" iddiası
> değildir. Projedeki tek kabul edilebilir kapı derleme komutu **`make verify`**
> (ruff + mypy --strict + bandit -ll + coverage `fail_under = 99` kapısıyla tam
> pytest); yukarıdaki tek-tek komutlar yalnızca geliştirme kolaylığıdır.
> Grep tabanlı sayımlarda `LC_ALL=C` kullanın — `tr_TR.UTF-8` yerel ayarında GNU
> grep `[A-Za-z]` aralıklarını sessizce yanlış çözüyor (README "Running Tests"
> notu).

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

1. Create a feature branch from **`master`** — depo dalının adı `master`'dır,
   `main` **değildir** (ölçüldü 2026-10-17: `git branch --show-current` →
   `master`, `cat .git/HEAD` → `ref: refs/heads/master`,
   `git symbolic-ref refs/remotes/origin/HEAD` → `refs/remotes/origin/master`).
   `main`'e açılan PR tarifi bir önceki belge kümesinden kalma ve bugün
   uygulandığında hedef dal bulunamaz.
2. Make your changes
3. Run the full test suite: `make verify` (tek gerçek kapı: ruff + mypy
   --strict + bandit -ll + pytest %99 kapsama eşiği ile). Tek-tek komut
   isterseniz: `python -m pytest tests/ -q`.
4. Run type check: `mypy core cli.py config.py main.py` and `ruff check .`
5. Update CHANGELOG.md if applicable
6. Submit PR with clear description

> **Not (2026-10-17 doğrulandı):** `@pytest.mark.slow` bu belgede önerilir
> ancak `pyproject.toml` yalnızca `bench` işaretçisini kaydeder
> (`markers = ["bench: …"]`); dolayısıyla `-m slow` ile seçme/filtering
> çalışmaz — suitin gerçekten atlayan tek işareti `bench`'tir.

## Plugin Development

To create a new converter plugin:

```python
from core.plugins import ConverterPlugin

class MyConverter(ConverterPlugin):
    name = "myformat"
    extensions = (".myformat",)
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
