# PkgForge — Genişleme Yol Haritası (Expansion Roadmap)

> **Bu belge bağlayıcıdır.** Kullanıcı 2026-08-22 tarihinde A, B ve C alanlarındaki
> TÜM maddelerin yapılmasını onayladı. Hiçbir madde atlanmayacak.
> UI mimarisi: **C-görsel (web/Tauri) + Python-sidecar** (Python core yeniden YAZILMAYACAK).
> Logo: **#1 Convergence — Mix 1** (Arch Blue #1793d1 × Ember #f97316, kesişim gradyan). FINAL.

## Faz Yapısı

- **Faz 0 — Tasarım Sistemi & Marka**: logo finali, renk/tipografi token'ları, ikon seti, C-görsel design system — ✅ tamamlandı (Tauri v2 + React + Python-sidecar; Convert/Installed/Settings parity; paketlenmiş sidecar; 637 Python + 26 vitest testi; sürüm 2.0.0-alpha)
- **Faz 1 — Alan A** (mevcut özellikleri GUI'ye taşı): A1–A6
- **Faz 2 — Alan B** (yeni yetenekler): B1–B8
- **Faz 3 — Alan C** (mimari genişleme): C1–C3

Her madde kendi *spec → plan → uygulama* döngüsünden geçecek.

---

## Alan A — Mevcut özellikleri GUI'ye taşı (hazır kod, UI wiring)

| # | Madde | Core modül(ler) | Durum |
|---|-------|-----------------|-------|
| A1 | Export merkezleri: AppImage / Flatpak / OCI container çıktısı | `appimage_converter`, `flatpak_converter`, `oci_builder` | ⬜ yapılacak |
| A2 | Güvenlik paneli: GPG imzala/doğrula, Sigstore, SBOM indir, SLSA provenance, kalite skoru | `package_signing`, `sigstore`, `sbom`, `provenance`, `quality_score` | ⬜ yapılacak |
| A3 | Bağımlılık görselleştirici: interaktif graf (ASCII/mermaid yerine) | `dep_graph`, `dep_resolver` | ⬜ yapılacak |
| A4 | Delta güncelleme yöneticisi: enable/disable/status + uygulama | `delta_updater` | ⬜ yapılacak |
| A5 | From-source sihirbazı: PKGBUILD üret → derle | `from_source` | ⬜ yapılacak |
| A6 | Sistem araçları: health check, audit log görüntüleyici, snapshot temizleyici, verify-rollback, benchmark | `cross_check`, `report_export`, `snapshot_cleanup`, `rollback_verify`, `benchmark` | ⬜ yapılacak |

## Alan B — Yeni yetenekler (yeni geliştirme)

| # | Madde | Durum |
|---|-------|-------|
| B1 | Paket tarayıcı/arama: AUR'da ara, popüler paketler, tek tıkla dönüştür | ⬜ yapılacak |
| B2 | Tray ikonu + masaüstü bildirimleri (arka planda güncelleme izleme) | ⬜ yapılacak |
| B3 | Zamanlanmış görevler (cron benzeri: "her gün 03:00'te güncelleme kontrolü") | ⬜ yapılacak |
| B4 | CVE/güvenlik açığı taraması (bağımlılıkları bilinen açıklarla karşılaştırma) | ⬜ yapılacak |
| B5 | Paket karşılaştırma: iki versiyonu diff'le (dosya listesi, boyut, bağımlılıklar) | ⬜ yapılacak |
| B6 | Toplu işlem iyileştirmeleri: filtreleme, önceliklendirme, paralel dönüştürme | ⬜ yapılacak |
| B7 | Web arayüzü: LAN üzerinden uzaktan yönetim | ⬜ yapılacak |
| B8 | Plugin pazarı UI: mevcut plugin sistemini görselleştir/yönet | ⬜ yapılacak |

## Alan C — Mimari genişleme

| # | Madde | Durum |
|---|-------|-------|
| C1 | REST API / D-Bus servisi (üçüncü taraf entegrasyonu; sidecar IPC'nin temeli) | ⬜ yapılacak |
| C2 | Çoklu profil: farklı ayar kümeleri (iş/kişisel) | ⬜ yapılacak |
| C3 | Bulut senkronizasyonu: ayarlar + geçmiş yedekleme | ⬜ yapılacak |

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
