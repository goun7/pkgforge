# PkgForge v2.1.0 — Sürüm Hazırlık Durumu

> Son doğrulama: 2026-09-07 · `make verify` · commit f6e0f74 sonrası
> Tarihsel notlar `docs/RELEASE_READINESS.md` (v1.1.0 dönemi) ve git
> geçmişindedir; bu dosya tek güncel kaynaktır.

## Ölçülen Gerçek Durum

| Alan | Durum | Kanıt |
|---|---|---|
| Test suit'i | **2576 test: 2572 passed, 4 skipped, 0 failed** | `pytest tests/ -q` (junit) |
| Kapsama | **%99** — 12 806 ifade, 47 eksik (`core/`+`ui/`+`i18n/`) | `--cov-fail-under=99` geçiyor |
| mypy | **0 hata** / 113 dosya (`core/`+`cli`+`main`+`config`+`ui/`, import takibi) | `make verify` |
| ruff | **0 hata** (0.16.4, CI-parite) | `ruff check .` |
| bandit | **temiz** (`-ll`, core+entry points) | CI-parite |
| i18n | **987/987** tr/en parite; CLI kullanıcı-yolu tam çeviri | `--lang en` duman testi |
| pip-audit | temiz | CI `supply-chain` job'u |
| Repo | **PUBLIC**, master korumalı (force-push/silme yasak) | `gh repo view` |
| Release boru hattı | gate (ruff+mypy+bandit+tam suit) → build → SBOM (SPDX+CycloneDX) + SLSA provenance + SHA256SUMS | `release.yml` |

## Bilinen başarısızlık: yok (2572 passed + 4 skipped, 0 failed)

Eskiden "pre-existing" sanılan 2 delta-timer testi bayat mock çıktı
(Faz-14 argv değişimine uyarlandı); ubuntu CI'daki kalan farklar
araç-guard'larıyla kapatıldı. CI yeşili release boru hattında izlenir.

## Kalan insan adımları

1. `v2.1.0` tag → release CI izlenir
2. Root `PKGBUILD` sha256 güncellenir (tag tarball'ından)
3. AUR: `pkgforge-git` (hazır, namcap-temiz) + `pkgforge` (stable) gönderimi
   — AUR hesabı + ssh anahtarı gerekir
4. debtap parite tablosunun debtap sütunu (`docs/BENCHMARK_PARITY.md` —
   root `debtap -u` gerektirir)
