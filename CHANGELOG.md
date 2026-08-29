# Changelog

All notable changes to PkgForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed
- **fix(desktop)**: abonelik unmount yarışı — `onEvent().then(push)` deseni
  erken unmount'ta sızıyordu; `rpc.ts`'de yeni `eventBinder()` ile 10 sayfa
  güvenli desene migrate edildi (33 çağrı noktası). Handler catch'lerinde
  bırakılan 9 tek-seferlik abonelik de kapatıldı.
- **fix(desktop)**: Browse abonelik effect'i her render'da kopup yeniden
  kuruluyordu (kararsız `t` bağımlılığı) — deps `[toast, lang]`.
- **fix(core)**: `subprocess_converters` ar/tar borusunda ar stderr okunmuyor-
  du → 64KB boru dolunca ölümkilit; ar/tar returncode kontrolü de yoktu
  (sessiz bozuk çıkarım). native_deb_converter parite deseni uygulandı.
- **test(desktop)**: `rpc.test.ts` eventBinder birim testleri (4); Python
  ar/tar hata-yolu testleri (2).

## [2.0.0] - 2026-08-27

### Added
- **feat**: Feature Tezgâhı Faz 2 — kalan CLI özellikleri `scan-image`,
  `attest`, `publish`, `snapshot-cleanup` her iki GUI'ye taşındı
  (`tools.*` RPC + PyQt6 4 sekme + Tauri 4 kart + `core.scan_oci_image`).
- **feat**: Fleet/kurumsal konsol (Alan D) — F5.18 sync backends (webdav/
  git/rclone-s3 + age) ve F5.19 politika motoru tek `fleet.status` RPC'sinde
  birleşti; PyQt6 FleetDialog + Tauri Fleet sayfası (backend/policy/profil/
  senkron özeti ve push/pull/export eylemleri).
- **feat**: UX modernizasyonu — 2026 standartları: motion tokenları,
  `prefers-reduced-motion` desteği, `focus-visible` klavye erişilebilirliği.

### Changed
- **test**: mutmut kalite kampanyası — `core/installer.py` mutant öldürme
  oranı **%34 → %99.1** (229 mutant / 227 öldürüldü; kalan 2 kanıtlanabilir
  eşdeğer mutant). FakeProcess + kesin-assert/argüman-yakalama testleri.

### Added (önceki)
- **support**: Gelir/bağış katmanı — `.github/FUNDING.yml` (GitHub
  Sponsors + Polar.sh + Kreosus), About dialoguna "Destek Ol" butonu
  (`config.DONATE_URL`), README destek bölümü, issue şablonları
  (bug/feature/config) ve strateji belgesi MONETIZATION_PLAN.md.

### Security
- **fix**: install_rehearsal container içi `sh -c` komutuna paket adı/klasörü
  quote'suz gömülüyordu (CWE-78) — shlex.quote ile kapatıldı; tam denetim
  SECURITY_REVIEW.md'de.

### Changed
- **refactor**: QProcess kullanan 5 sinifa (deb/rpm/native_deb donusturucu,
  installer, distrobox_fallback) process_factory enjeksiyonu — testler
  somut QProcess yerine sahte surec verebilir.
- **fix**: sessiz `except: pass` bloklarina debug log eklendi (abi_scanner,
  aur_publish, benchmark, dbus_service, dep_graph, from_source);
  `_estimate_size_mb` okunamayan girdiyi tum tahmini bozmak yerine
  atlayip logluyor; `find_privileged_helper` fallback'te uyari veriyor.
- **chore**: diger oturumun bekleyen kozmetik duzenlemeleri commit edildi
  (7c79ac7).


### Added
- **tests**: Oturum-3 100/100 taramasi — package_signing, cli_bridge,
  capabilities, upstream_tracker, benchmark, snapshot_manager,
  offline_cache %100; privileged/distrobox/cloud_sync/rehearsal/
  structured_log/sigstore/aur_publish/rpm-flatpak-appimage donusturuculeri,
  styles, snapshot_cleanup, oci_builder, delta_updater, profiles,
  queue_manager, provenance, sbom, aur_checker kalan dallari (+142 test);
  toplam kapsama **%97 → %100** (10 541 stmt, **0 eksik**), **2147 test**.
- **tests**: Oturum-2 final sprint — api_server %100,
  compatibility_checker %100, abi_scanner %100, installer %100,
  dbus_service %100, cve_scanner %100, secrets_store/plugins %100
  (+~90 yeni test); toplam kapsama **%89 → %97** (10 541 stmt,
  307 eksik), **2005+ test**.