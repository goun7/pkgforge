# Changelog

All notable changes to PkgForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed
- **fix(ux)**: sudo/pkexec bombardımanı — delta/snapshot kurulumları tek işlemde
  4-5 ayrı parola diyalogu açıyordu. Yeni `write-batch` helper alt-komutu tüm
  dosyaları TEK pkexec diyaloğunda yazar; systemctl fiilleri (enable/start/
  stop/daemon-reload) artık helper üzerinden yetkili gider (eskiden yetkisiz
  çağrılıp sessizce başarısız oluyordu). Tam analiz: docs/SUDO_DENETIMI_FAZ14.md.
- **fix(packaging)**: gerçek polkit policy'si (`org.pkgforge.helper.policy`,
  auth_admin_keep) hiçbir yere kurulmuyordu — pkexec her çağrıda genel
  auth_admin fallback'ine düşüyordu. Artık wheel data-files + install.sh
  kuruyor; helper betikleri /usr/share/pkgforge/scripts'e root-0755 gider.
- **fix(delta)**: timer aralığı yok sayılıyordu (12 saat seçilse bile sabit
  6h OnCalendar). 24'ün bölenleri OnCalendar adımı, diğerleri OnUnitActiveSec.
- **fix(api)**: kurulum rotası doğrudan `pkexec pacman` yerine konsolide
  helper `install-pkg`'ye geçti (tek policy action + argüman doğrulaması).
- **test**: tek-diyalog sözleşmesi testlerle kilitlendi (write-batch çağrı
  sayısı = 1 assert'i; timer aralık yansıması; ret-kod yüzeyi).
- **feat(doctor)**: `pkgforge doctor` artık polkit teşhisi basıyor — policy
  kurulu mu, helper sisteme mi kurulu, kaynak ağacından mı çalışılıyor;
  "bolca sudo isteği" belirtisi görünür kök nedenine bağlanıyor.
- **feat(desktop)**: Doktor kartında Yetki (polkit) satırı: policy eksikse
  uyarı rengiyle teşhis detayı + tek-parola çözüm önerisi (install.sh) kutusu;
  kopyalanan tanı Markdown'ına `polkit.ok` bölümü düşer (tr/en).
- **fix(desktop)**: Settings: profil silme artık onaylı (ConfirmDialog — tek
  tıkla yıkıcı silme kalktı); Kaydet'in yanında "Kaydedilmemiş değişiklikler
  var" göstergesi (dirty-state; save/reset/import sonrası temizlenir).
- **fix(desktop)**: Convert: "Kuyruğu Temizle" artık onaylı — bekleyen tüm
  dönüşüm görevleri tek tıkla silinmiyor (Vazgeç = RPC yok; onay = queue.clear).
- **fix(desktop)**: Reports: snapshot temizlik servisi "Kaldır" işlemi (systemctl
  stop/disable + sistem dosyası silme) onaylı; Updates: delta zamanlayıcı
  "Kapat" işlemi onaylı (systemctl disable + dosya silme). i18n tr/en.
- **refactor(core)**: `score_package` 341 → 37 satır orkestratör; güvenlik/
  uyumluluk/üstveri/boyut denetimleri kategori fonksiyonlarına ayrıldı
  (davranış birebir; quality testleri 51/51, ruff+mypy temiz).
- **fix(desktop)**: PathPicker'da dialog reddi yakalanmıyordu — browse hatası
  yakalanmamış promise reddi üretiyordu; artık sessizce atlanıp kilit düşüyor.
- **test(desktop)**: kapsam %88.7 → %90.1: LogViewer %43.75→%84.37,
  SidecarGuard %53.84→%100, TopbarActions/PathPicker dalları, Dialog odak
  tuzağı + backdrop/başlıksız/odak-geri-dönüş (10/10). 552→557 test.
- **test(desktop)**: kapsam %90.1 → %92.86: Installed %54.47→%88.61
  (sıralama/CSV/sayfalama/temizle+geri-al/rollback), Sidebar %68.75→%100
  (kompakt mod/bölüm daraltma/localStorage hata dalı), Dialog %55.55→%93.33.
  557→571 test.
- **test(desktop)**: Faz 20b act() hijyeni: Convert/Updates render
  helper'ları async act flush; 36+ emit çağrısı await act'e çevrildi; sync
  testler async yapıldı. act uyarı 551→282 (kalanlar çok-tick promise
  zincirleri — test diagnostics'i, hata değil). 578/578, tsc 0.
- **test(desktop)**: Faz 20c: sekiz sayfa testine (Fleet/Tools/Reports/
  Export/Compare/Browse/Plugins/Security) aynı act reçetesi; WebDAV
  push/pull dalları Settings'te kapatıldı (sync.push/sync.pull + boş
  URL disabled). Uyarı 551→224; kapsam %93.1 (Settings %71.1); 580/580.
- **report**: Faz 21a kapanış değerlendirmesi — ruff 0, mypy 77 dosya
  0 hata, pytest rc=0 (~2460+ test), vitest 580/580, tsc 0, kapsam %93.1;
  act diagnostics 551→224; _temp_dir guard + WebDAV push/pull dalları.
- **refactor(core)**: Faz 18b dev fonksiyonlar — run_benchmarks 140→29
  (7 benç yardımcısı), verify_reproducible 132→~50 (extract/rebuild/compare),
  generate_sbom 123→~30 (4 yardımcı), install_auto_update 111→30
  (_find_systemctl/_auto_update_units/_write_and_enable_units). Kalan ≥100:
  6 (Handler fabrikası yanlış pozitif dahil).
- **refactor(core)**: Faz 18c: RpmConverterSubprocess._do_convert 106→~35
  (_rpm_extract/_rpm_security_gate/_rpm_makepkg_build/_find_pkg_artifact).
  Yanlış-sınıf düzenlemesi git-restore ile kurtarıldı. Kalan ≥100: 5
  (4'ü yeni tur adayı, _make_http_handler sınıf fabrikası — kabul).
- **refactor(core)**: Faz 18d: download_package 102→~80
  (_validate_download_url/_download_filename/_verify_download_sha256;
  HTTPS-zorunlu ve SHA teyit semantiği aynen). Kalan ≥100: 4 kabul
  (şablon üreteci + sınıf fabrikası) + 2 hafif aday.
- **refactor(core)**: Faz 18e: check_abi_compatibility 103→~55
  (_extract_pkg_for_abi/_collect_elf_binaries/_ldd_missing_libs) ve
  build_file_dep_graph 100→~55 (_extract_for_graph/_graph_elf_candidates/
  _ldd_graph_edges). ≥100 satır envanteri KAPANDI — kalan 2 kabul
  edilmiş (PKGBUILD şablon üreteci 112; Handler sınıf fabrikası 138,
  iç metodlar ≤31).
- **test(desktop)**: Faz 22 kapanış cilası: Settings yedek-yolu onChange +
  sync.export, WebDAV user/pass yazımı (+2 test). Convert browse-diyalog
  testine flaky koruması (explicit flush + 5s waitFor). 580→582 test,
  kapsam %93.1→%93.22.
- **refactor(core)**: Faz 20 dev fonksiyonlar bölündü — davranış birebir:
  _run_pipeline 206→43 satır (_stage_security/_stage_malware/_stage_analysis/
  _stage_conversion); serve_http 175→33 (_http_validate_bind +
  _make_http_handler fabrikası); _check_shared_libraries 144→76
  (_list_package_elf_files + _analyze_elf_dependencies + _shared_lib_result,
  ldd yasağı korunur).
- **test(desktop)**: kapsam %92.86 → %93.06: Settings %68.44→%70.22
  (profil hata yolları/radio geçişi/sync.import/sync.config/dbus başlat ve
  yok durumu). 571→578 test.

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