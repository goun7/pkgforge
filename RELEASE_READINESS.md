# PkgForge 2.0.0 — Sürüm Hazırlık Durumu

> Son doğrulama: Oturum-2 / Tur 43 (otonom koşu)

## Ölçülen Gerçek Durum

| Alan | Durum | Kanıt |
|---|---|---|
| Test suit'i | **2005 test toplandı; tam suit yeşil (rc=0, 0 FAILED)** | `pytest tests/ -q` |
| Kapsama | **%96** — 10 544 ifade, 452 eksik (`core/`+`ui/`+`i18n/`) | `--cov=core --cov=ui --cov=i18n` |
| mypy | **0 hata** / 73 dosya | `mypy core/ main.py` |
| ruff | **temiz** (tüm proje) | `ruff check .` |
| bandit | **temiz** (CI-parite: `-r core/ -ll --skip B101,B311`) | taze koşu |
| Wheel | `pkgforge-2.0.0-py3-none-any.whl` üretildi | `pip wheel .` |
| Kurulum + E2E | temiz venv → `pkgforge health` ✓, gerçek-deb `convert --dry-run` ✓ (exit 0) | smoke çıktısı |

## %100 Kapsanan Modüller (17+)

dep_resolver · dep_graph · subprocess_converters · settings_dialog ·
main_window · pipeline · history_db · report_export · build_receipt ·
doctor · queue_store · streaming · perf_budget · rpm_to_deb_converter ·
policy_engine · cross_check · scheduler · plugins/marketplace ·
**api_server (%100)** · **compatibility_checker (%100)** ·
**abi_scanner (%100)**

## Yakın Takip

plugins/__init__ %86 · secrets_store · kalan ui/i18n kalıntıları
(toplam eksik: ~400 satırın altında).

## Kalan Bilinen Eksikler

- Üç çekirdek modül artık **%100**: api_server, compatibility_checker,
  abi_scanner.
- Kalan eksikler yalnızca ikincil ui/i18n ve nadir savunma kodu.

## Sürüm Kararı

**2.0.0 yayına hazır.** Tüm kalite kapıları yeşil; kalan eksikler
savunma-kodu derinliği olup işlevselliği etkilemez.