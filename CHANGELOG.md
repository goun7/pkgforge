# Changelog

All notable changes to PkgForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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