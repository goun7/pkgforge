# Changelog

All notable changes to PkgForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **tests**: Oturum-2 final sprint — api_server %57→%96 (HTTP yüzeyi,
  işleyici katmanı, SSE), compatibility_checker %94, abi_scanner %97,
  plugins/marketplace %100 (+~60 yeni test); toplam kapsama **%89 → %96**
  (10 544 stmt, 452 eksik), **2005 test**.

### Verified
- Statik üçlü: mypy 0 hata (73 dosya) · ruff tüm-proje temiz ·
  bandit CI-paritesi temiz.
- Wheel doğrulaması: `pkgforge-2.0.0` whl üretildi; temiz venv'e kuruldu;
  `pkgforge health` ve gerçek-deb `convert --dry-run` E2E koşuldu.
- **tests**: Oturum-2/3 kapsam maratonu — dep_resolver %73→%100,
  dep_graph %41→%100, subprocess_converters %86→%100,
  main_window %50→%92, settings_dialog %84→%100 (+~120 yeni test);
  toplam kapsama **%80 → %86** (core+ui+i18n), toplam **1772 test**.
