# PkgForge v2.1.0 — Sürüm Hazırlık Durumu

> Son doğrulama: 2026-09-07 · `make verify` · commit f6e0f74 sonrası
> Tarihsel notlar `docs/RELEASE_READINESS.md` (v1.1.0 dönemi) ve git
> geçmişindedir; bu dosya tek güncel kaynaktır.

## Ölçülen Gerçek Durum

| Alan | Durum | Kanıt |
|---|---|---|
| Test suit'i | **2521 test: 2514 passed, 5 skipped, 2 pre-existing env-fail** | `pytest tests/ -q` (junit) |
| Kapsama | **%99** — 12 746 ifade, 118 eksik (`core/`+`ui/`+`i18n/`) | `--cov-fail-under=99` geçiyor |
| mypy | **0 hata** / 95 dosya (`core/`+`cli`+`main`+`config`, import takibi) | `make verify` |
| ruff | **0 hata** (0.16.4, CI-parite) | `ruff check .` |
| bandit | **temiz** (`-ll`, core+entry points) | CI-parite |
| i18n | **987/987** tr/en parite; CLI kullanıcı-yolu tam çeviri | `--lang en` duman testi |
| pip-audit | temiz | CI `supply-chain` job'u |
| Repo | **PUBLIC**, master korumalı (force-push/silme yasak) | `gh repo view` |
| Release boru hattı | gate (ruff+mypy+bandit+tam suit) → build → SBOM (SPDX+CycloneDX) + SLSA provenance + SHA256SUMS | `release.yml` |

## Bilinen 2 başarısızlık (çevresel, temiz ağaçta da patlar)

- `test_delta_enable_start_fail`, `test_install_auto_update_service_write_fail`
  — systemd/pkexec bağımlı; CI (ubuntu, systemd'li) ve Arch makinede
  ayrıca değerlendirilir.

## Kalan insan adımları

1. `v2.1.0` tag → release CI izlenir
2. Root `PKGBUILD` sha256 güncellenir (tag tarball'ından)
3. AUR: `pkgforge-git` (hazır, namcap-temiz) + `pkgforge` (stable) gönderimi
   — AUR hesabı + ssh anahtarı gerekir
4. debtap parite tablosunun debtap sütunu (`docs/BENCHMARK_PARITY.md` —
   root `debtap -u` gerektirir)
