# PkgForge — Genişleme Yol Haritası (Expansion Roadmap)

> **Bu belge bağlayıcıdır.** Kullanıcı 2026-08-22 tarihinde A, B ve C alanlarındaki
> TÜM maddelerin yapılmasını onayladı. Hiçbir madde atlanmayacak.
> UI mimarisi: **C-görsel (web/Tauri) + Python-sidecar** (Python core yeniden YAZILMAYACAK).
> Logo: **#1 Convergence — Mix 1** (Arch Blue #1793d1 × Ember #f97316, kesişim gradyan). FINAL.

## Faz Yapısı

- **Faz 0 — Tasarım Sistemi & Marka**: logo finali, renk/tipografi token'ları, ikon seti, C-görsel design system — ✅ tamamlandı (Tauri v2 + React + Python-sidecar; Convert/Installed/Settings parity; paketlenmiş sidecar; 637 Python + 26 vitest testi; sürüm 2.0.0-alpha)
- **Faz 1 — Alan A** (mevcut özellikleri GUI'ye taşı): A1–A6 — ✅ tamamlandı (sidecar method'ları + Security/Updates/Reports/Export sayfaları + DepGraph + Convert genişletmeleri; 656 Python + 45 vitest testi)
- **Faz 2 — Alan B** (yeni yetenekler): B1–B8 — ✅ tamamlandı (AUR tarayıcı, tray+bildirim, zamanlayıcı, CVE taraması, paket karşılaştırma, toplu kuyruk, HTTP/LAN API, plugin pazarı; kritik event-adı düzeltmesi; 686 Python + 57 vitest testi)
- **Faz 3 — Alan C** (mimari genişleme): C1–C3 — ✅ tamamlandı (çoklu profil, yedek/WebDAV senkron, D-Bus servisi; kritik event-adı düzeltmesi sonrası; 727 Python + 64 vitest testi)
- **Faz 4 — Sertleştirme** (eleştiri kaynaklı 11 madde): F4.1 event sözleşme testi, F4.2 HTTP token zorunluluğu + hız/gövde limitleri + D-Bus salt-okunur politika, F4.3 toplu kuyruk dürüstlüğü (salt-dönüşüm varsayılan, kayıt defteri + cancel), F4.4 anahtarlık (Secret Service), F4.5 yedek bütünlüğü (WAL checkpoint + sha256 manifest), F4.6 systemd timer + headless CLI, F4.7 polkit policy tek-kaynak, F4.8 OpenAPI/Swagger, F4.9 web panosu, F4.10 sürüm tek-kaynağı (2.0.0) + CI (ruff/frontend/cargo), F4.11 i18n köprüsü — ✅ tamamlandı; 765 Python (+3 skip) ve 67 vitest testi; E2E 4/4
- **Faz 5 — Mükemmelleştirme** (Faz 4 sonrası eleştiriler C1–C20 + 20 yaratıcı öneri S1–S20 → F5.1–F5.26): ✅ **TAMAMLANDI (26/26)**. Sertleştirme/borç: F5.1 capabilities tek-kaynak + D-Bus arayan-UID (fail-closed -32002), F5.2a token-file/env + rate-map budama, F5.2b --insecure-http-lan + --trusted-proxy XFF, F5.3 systemd sandbox, F5.4 pkexec tek helper (pkgforge-privileged.sh) + eylem-bazlı exec.path, F5.5 swagger vendor + CSP + HTML→http_assets, F5.6 keyring canlı CI + OpenSession marshalling, F5.7 hypothesis import_backup fuzz, F5.9 83 legacy ruff sıfırlandı, F5.10a badge + Cargo parity, F5.11 api_server→core/http_api/ (meta+read router, facade), F5.12 kuyruk sqlite kalıcılığı+restore, F5.13 METHODS→TS codegen + CI diff-check. Ürün: F5.14 install.rehearse (konteyner provası), F5.15 provenance makbuzu (araç sürümleri+debtap-db→attest/SBOM), F5.16 delta DENEYSEL etiketi, F5.17 restore_drill görevi, F5.18 fleet sync backends (git/rclone-s3)+age, F5.19 politika motoru+Settings, F5.20 Convert canlı dil, F5.21 AppStream+flatpak, F5.22 pkgforge doctor, F5.23 SSE GET /events, F5.24 Stats Wrapped, F5.25 upstream enrichment, F5.26 perf bütçesi (%20). Testler: **906 Python (+6 skip), 74 vitest**; ruff/mypy temiz; desktop build temiz.
  - **F5.8 mutmut pilot durumu:** mutmut 3.7 kuruldu ve `pyproject.toml [tool.mutmut]` yapılandırıldı (kaynak: core/installer.py, test: tests/test_converter_guards.py). Ancak mutmut 3.x kaynakları izole bir `mutants/` dizinine kopyalıyor; bu projenin üst-seviye modülleri (`config`, `i18n`) o dizinde import edilemediği için conftest `ModuleNotFoundError` veriyor ve 0 mutant üretiliyor. ✅ **ÇÖZÜLDÜ (2026-08-25, oturum-2):** conftest iki kök sorunu çözdü — (1) orijinal kök üst-seviye modüller (`config`, `i18n`) için `sys.path`'e APPEND edilir; (2) kritik Python kuralı gereği `__init__.py` taşıyan orijinal `core/` mutant kopyayı gölgelediğinden conftest, mutant bağlamında `mutants/core/__init__.py` yazıp `__path__` ile orijinal core'a köprüler. Test eşi de `tests/test_installer_units.py` olarak düzeltildi. İlk tam koşu: **226 mutant / 78 öldürüldü (~%35) / 109 hayatta / 39 kapsamsız**. ✅ **KAMPANYA (2026-08-27, Tur-64):** `tests/test_installer_units.py`'ye FakeProcess + kesin-assert/argüman-yakalama testleri eklendi (install mutlu-yol + snapshot bloğu + cancel/_on_output/_on_error/_find_helper/_verify). Sonuç: **229 mutant / 227 öldürüldü (%99.1) / 2 hayatta / 0 kapsamsız** — kalan 2 mutant `_on_output`'taki kanıtlanabilir eşdeğer mutantlar (`bytes.decode()` utf-8 varsayılanı ve `"UTF-8"` codec aliası). Çalıştırma: `rm -rf mutants && .venv/bin/mutmut run` (test değişince `mutants/` silinmeli, yoksa cache'ten okur). CI'a süre gereği hâlâ alınmadı.

Her madde kendi *spec → plan → uygulama* döngüsünden geçecek.

---

## Alan A — Mevcut özellikleri GUI'ye taşı (hazır kod, UI wiring)

| # | Madde | Core modül(ler) | Durum |
|---|-------|-----------------|-------|
| A1 | Export merkezleri: AppImage / Flatpak / OCI container çıktısı | `appimage_converter`, `flatpak_converter`, `oci_builder` | ✅ Faz 1 (Export sayfası + Convert OCI butonu) |
| A2 | Güvenlik paneli: GPG imzala/doğrula, Sigstore, SBOM indir, SLSA provenance, kalite skoru | `package_signing`, `sigstore`, `sbom`, `provenance`, `quality_score` | ✅ Faz 1 (Security sayfası) |
| A3 | Bağımlılık görselleştirici: interaktif graf (ASCII/mermaid yerine) | `dep_graph`, `dep_resolver` | ✅ Faz 1 (DepGraph SVG bileşeni) |
| A4 | Delta güncelleme yöneticisi: enable/disable/status + uygulama | `delta_updater` | ✅ Faz 1 (Updates sayfası; pkexec Faz 2) |
| A5 | From-source sihirbazı: PKGBUILD üret → derle | `from_source` | ✅ Faz 1 (Convert/Kaynaktan sekmesi) |
| A6 | Sistem araçları: health check, audit log görüntüleyici, snapshot temizleyici, verify-rollback, benchmark | `cross_check`, `report_export`, `snapshot_cleanup`, `rollback_verify`, `benchmark` | ✅ Faz 1 (Reports sayfası; pkexec Faz 2) |

## Alan B — Yeni yetenekler (yeni geliştirme)

| # | Madde | Durum |
|---|-------|-------|
| B1 | Paket tarayıcı/arama: AUR'da ara, popüler paketler, tek tıkla dönüştür | ✅ Faz 2 (Browse sayfası + search_aur + aur.build) |
| B2 | Tray ikonu + masaüstü bildirimleri (arka planda güncelleme izleme) | ✅ Faz 2 (Tauri tray + notification plugin) |
| B3 | Zamanlanmış görevler (cron benzeri: "her gün 03:00'te güncelleme kontrolü") | ✅ Faz 2 (schedule.* + scheduler thread) |
| B4 | CVE/güvenlik açığı taraması (bağımlılıkları bilinen açıklarla karşılaştırma) | ✅ Faz 2 (cve_scanner.py + OSV.dev) |
| B5 | Paket karşılaştırma: iki versiyonu diff'le (dosya listesi, boyut, bağımlılıklar) | ✅ Faz 2 (Compare sayfası + diff_sboms) |
| B6 | Toplu işlem iyileştirmeleri: filtreleme, önceliklendirme, paralel dönüştürme | ✅ Faz 2 (queue.* + Convert/Toplu sekmesi) |
| B7 | Web arayüzü: LAN üzerinden uzaktan yönetim | ✅ Faz 2 (serve --http, bearer token) |
| B8 | Plugin pazarı UI: mevcut plugin sistemini görselleştir/yönet | ✅ Faz 2 (Plugins sayfası + plugin.*) |
| B9 | Evrensel girdi katmanı: .deb/.rpm ötesi her türü (kaynak/binary tar.gz, AppImage, kaynak klasör, Arch paketi) tek UI-üstü kapıdan kabul et; belirsiz tar.gz için kaynak/binary seçimi | ✅ Faz 4 (`core/intake.py` sınıflandırıcı + pipeline rota + PyQt6 & Tauri UI + sidecar `mode` parametresi) |
| B10 | Feature Tezgâhı: kalan CLI özelliklerini (RPM→DEB, ABI denetimi, denetim izi/audit) her iki GUI'ye taşı | ✅ Faz 5 (`tools.*` RPC + PyQt6 ToolsDialog + Tauri Tools sayfası) |
| B11 | UX modernizasyonu: 2026 standartları (motion tokenları, prefers-reduced-motion, focus-visible klavye erişilebilirliği) | ✅ Faz 5 (tokens.css/index.css + Sidebar/Button) |
| B12 | Feature Tezgâhı Faz 2: kalan CLI özellikleri scan-image/attest/publish/snapshot-cleanup'ı her iki GUI'ye taşı | ✅ Faz 5 (`tools.*` RPC + PyQt6 4 sekme + Tauri 4 kart + `scan_oci_image` core) |
| B13 | Fleet/kurumsal konsol (Alan D): F5.18 sync backends + F5.19 policy'yi tek konsolda birleştir (backend/policy/profil/senkron) | ✅ Faz 5 (`core/fleet.py` + `fleet.status` RPC + PyQt6 FleetDialog + Tauri Fleet sayfası) |

## Alan C — Mimari genişleme

| # | Madde | Durum |
|---|-------|-------|
| C1 | REST API / D-Bus servisi (üçüncü taraf entegrasyonu; sidecar IPC'nin temeli) | ✅ Faz 3 (serve --http JSON-RPC + jeepney D-Bus köprüsü org.pkgforge.App) |
| C2 | Çoklu profil: farklı ayar kümeleri (iş/kişisel) | ✅ Faz 3 (profile.* + profil başına ayar/geçmiş, Settings kartı) |
| C3 | Bulut senkronizasyonu: ayarlar + geçmiş yedekleme | ✅ Faz 3 (profil-farkındalıklı zip yedek + WebDAV push/pull) |

---

## UI Mimari Kararı (2026-08-22)

```
┌─────────────────────────────────────────┐
│  Tauri kabuk (Rust, native pencere)      │
│  ├─ Web frontend: React/Svelte + Tailwind│  ← 10/10 UI (C mockup estetiği)
│  └─ IPC / yerel HTTP                     │
└──────────────┬──────────────────────────┘
               │ sidecar (mevcut Python, DEĞİŞMEDEN)
┌──────────────▼──────────────────────────┐
│  PkgForge Python core                    │
│  45 modül · 627+ test · pipeline · güvenlik│
└─────────────────────────────────────────┘
```

## Marka Kararları (2026-08-22)

- Logo konsepti: **#1 Convergence** (iki paket → kesişimde Arch paketi)
- Renk: **Mix 1 — FINAL** (Arch Blue #1793d1 × Ember #f97316, kesişim mavi→turuncu gradyan)
- Final assetler: `assets/logo/` (SVG master, PNG 16–1024px, ICO çoklu-boyut, macOS iconset)
- Mockup'lar: `docs/design/mockups/`, logo turları: `docs/design/logos/`
