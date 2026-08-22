# Faz 0 — Tasarım Sistemi & Marka (Design System & Brand)

**Tarih:** 2026-08-22 · **Durum:** Onaylandı · **Sürüm hedefi:** 2.0.0-alpha

## 1. Amaç ve Kapsam

PkgForge'un arayüzünü "C-görsel" (modern SaaS dashboard estetiği) ile yeniden inşa
etmek için gerekli temeli kurmak: marka varlıkları, tasarım token'ları, bileşen
kütüphanesi ve Tauri + Python-sidecar mimari iskeleti. Faz 0 bittiğinde Convert
akışı yeni UI'da uçtan uca gerçek pipeline üzerinden çalışır.

**Kapsam dışı:** Alan A/B/C özellik maddeleri (Faz 1–3), Python core'un yeniden
yazılması (asla yapılmayacak), PyQt6 GUI'nin kaldırılması (parity sağlanana kadar kalır).

## 2. Marka Temeli

### 2.1 Logo (FINAL)

- Konsept: **#1 Convergence — Mix 1**: iki yuvarlatılmış kare (.deb = Arch Blue,
  .rpm = Ember) üst üste biner; kesişim = mavi→turuncu gradyan dolu Arch paketi.
- Renkler: Arch Blue `#1793d1`, Ember `#f97316`, gradyan kesişim.
- Assetler: `assets/logo/` — SVG master (dark/light/transparent/appicon),
  PNG 16–1024px, çoklu-boyut ICO (16/24/32/48/64/128/256), macOS iconset.
- Küçük boyut kuralı: 16px'de iki kare + merkez blok okunur (doğrulandı).

### 2.2 Renk Token'ları (dark-first)

| Token | Değer | Kullanım |
|---|---|---|
| `--brand-blue` | `#1793d1` | Birincil marka rengi, ana aksiyonlar |
| `--brand-ember` | `#f97316` | İkincil marka rengi, vurgu, forge anları |
| `--brand-gradient` | `#1793d1 → #f97316` | Logo, hero, başarı |
| `--bg-base` | `#0a0e1a` | Ana koyu zemin |
| `--bg-surface` | `#121829` | Kart/yüzey |
| `--bg-elevated` | `#1a2038` | Hover/aktif yüzey |
| `--text-primary` | `#e8ecf4` | Ana metin |
| `--text-secondary` | `#8b95a8` | İkincil metin |
| `--text-muted` | `#5a6478` | Soluk metin |
| `--success` | `#10b981` | Başarı/kuruldu |
| `--warning` | `#f59e0b` | Uyarı |
| `--danger` | `#ef4444` | Hata/kaldır |
| `--info` | `#38bdf8` | Bilgi |

Light tema: aynı token adları, `--bg-base: #f8fafc`, `--bg-surface: #ffffff`,
`--text-primary: #111827`, marka renkleri koyulaştırılmış (`#0e7ab5`, `#d95f0e`).

### 2.3 Tipografi

- UI: **Inter** (400/600/700/800) — self-hosted, sistem fontuna fallback.
- Mono: **JetBrains Mono** — log panel, hash, SHA, PKGBUILD önizleme.
- Ölçek: 11/12/13/14/16/20/24px.

### 2.4 Uzamsal Token'lar ve İkonlar

- Boşluk tabanı: 4px (4/8/12/16/24/32).
- Yarıçap: 8px buton, 12px input, 16px kart, 24px modal.
- Gölge: sm/md/lg; koyu temada subtle teal/ember glow.
- İkon seti: **Lucide** (stroke-based, 1.5px, tree-shakeable).

## 3. Mimari

### 3.1 Katmanlar

```
Tauri v2 (Rust) — native pencere, tray, bildirim, dosya sistemi erişimi
  ├─ Frontend: React 19 + TypeScript + Vite
  │    Tailwind CSS v4 + shadcn/ui + Framer Motion + Lucide + ⌘K palet
  └─ IPC: Tauri commands → sidecar relay
Python sidecar — core/api_server.py (JSON-RPC 2.0 over stdio)
  └─ Mevcut 45 core modülü DEĞİŞMEDEN kullanılır
```

### 3.2 IPC Protokolü (JSON-RPC 2.0 over stdio)

- HTTP portu AÇILMAZ (güvenlik yüzeyi sıfır); iletişim yalnızca stdin/stdout.
- Request/response: standart JSON-RPC 2.0 (`id`, `method`, `params`).
- Event stream: sidecar → UI tek yönlü bildirimler (`method` alanında
  `event.*` öneki, `id` yok): `event.step_changed`, `event.progress`,
  `event.log`, `event.compatibility_ready`, `event.finished`.
- Methodlar (Faz 0): `pipeline.start`, `pipeline.cancel`, `pipeline.approve`,
  `pipeline.dismiss`, `history.list`, `history.uninstall`, `history.rollback`,
  `settings.get`, `settings.set`, `tools.status`, `app.version`.
- Her method mevcut core fonksiyonlarını çağırır; yeni iş mantığı YAZILMAZ.
- Satır tabanlı çerçeveleme: her mesaj tek satır JSON + `\n`.

### 3.3 Sidecar Yaşam Döngüsü

- Tauri uygulamayı açınca sidecar'ı başlatır (`spawn`), kapanışta öldürür.
- Geliştirme modu: `python main.py serve` (kaynak ağaçtan).
- Üretim: PyInstaller tek dosya binary, Tauri bundle'ına gömülü.
- Sidecar çökerse UI "bağlantı koptu" banner'ı gösterir + otomatik yeniden başlatma (3 deneme).

### 3.4 Geçiş Stratejisi

- PyQt6 GUI çalışmaya devam eder (`pkgforge gui`); yeni UI ayrı giriş (`pkgforge desktop`).
- Parity sağlanana kadar ikisi birlikte dağıtılır; 2.x'te varsayılan yeni UI olur.
- Python core'a dokunulmaz; yalnızca yeni `core/api_server.py` eklenir.

## 4. Bileşen Kütüphanesi

shadcn/ui tabanlı, token'larla temalanmış bileşenler:

- **Primitifler:** Button, IconButton, Card, Badge, Input, Select, Checkbox,
  Switch, Table, Dialog, Toast, Tabs, Tooltip, Skeleton, ProgressBar.
- **Kompozitler:** Sidebar (sol navigasyon), Topbar (⌘K arama + aksiyonlar),
  CommandPalette, StepIndicator (5 aşamalı pipeline), DropZone (drag-drop +
  animasyonlu), QueueList, LogViewer (renk kodlu, sanal kaydırmalı),
  EmptyState, StatusPill, ConfirmDialog (tehlikeli işler için tip-onayı opsiyonu).

## 5. Ekranlar ve Faz 0 Kapsamı

| Ekran | Faz 0 | Not |
|---|---|---|
| Convert (dropzone + kuyruk + aktivite) | TAM | Gerçek pipeline, ERROR'da "Yine de Kur" dahil |
| Installed (geçmiş/kaldır/rollback) | TAM | HistoryDB parity |
| Settings (dil/tema/özellikler) | TAM | i18n parity (tr/en) |
| Browse / Updates / Security / Reports / Plugins | İSKELET | Boş durum + "Faz 1–2'de" etiketi |

**Başarı kriteri (dikey dilim):** dosya seç → güvenlik → analiz → dönüşüm →
uyumluluk → kurulum akışı; WARNING/ERROR'da karar diyaloğu; iptal; kuyruk;
log panel — tümü sidecar üzerinden hatasız.

## 6. Test Stratejisi

- Mevcut 627 Python testi aynen korunur ve CI'da çalışmaya devam eder.
- `core/api_server.py` için pytest protokol testleri (her method + event akışı).
- Frontend: Vitest + Testing Library (bileşen testleri).
- E2E: Playwright (web katmanı) + Tauri driver (entegrasyon).
- Sidecar mock'u ile frontend, Python'a bağımlı olmadan test edilebilir.

## 7. Paketleme ve Dağıtım

- Tauri bundler: uygulamanın kendi `.deb`/`.rpm`/`.AppImage`/`.pkg.tar.zst`'ı.
- Sidecar: PyInstaller `--onefile`, Tauri `externalBin` ile gömülü.
- AUR: mevcut `pkgforge` (CLI+PyQt6) sürer; yeni UI için ileride `pkgforge-desktop`.
- Repo PRIVATE kalmaya devam eder; yayın kullanıcının açık onayına bağlıdır.

## 8. Kilometre Taşları

1. **M0.1** Token'lar + logo entegrasyonu (favicon, app icon, splash)
2. **M0.2** Tauri iskelet + JSON-RPC protokolü + `core/api_server.py`
3. **M0.3** Bileşen kütüphanesi (tüm design system parçaları)
4. **M0.4** Convert dikey dilimi (uçtan uca gerçek pipeline)
5. **M0.5** Installed + Settings parity
6. **M0.6** Paketleme + E2E + `2.0.0-alpha` etiketi

## 9. Riskler ve Karşı Önlemler

| Risk | Karşı önlem |
|---|---|
| PyInstaller + Python 3.14 uyumu | Erken M0.2'de proof-of-concept; gerekirse Nuitka |
| Tauri webview sistem bağımlılığı (webkit2gtk) | Arch/CachyOS'ta hazır; belgelenir |
| Sidecar gecikmesi UI'yı yavaşlatır | Event stream + optimistic UI + skeleton |
| PyQt6 ve yeni UI paralel bakım yükü | Parity sonrası PyQt6 GUI dondurulur |
| Kapsam kayması | Faz 0 yalnızca bu belgedeki kapsam; A/B/C maddeleri Faz 1–3'te |

## 10. Bağlayıcı Referanslar

- 17 maddelik genişleme listesi: `docs/ROADMAP.md` (A1–A6, B1–B8, C1–C3).
- UI mockup: `docs/design/mockups/03-ui-path-C-tauri-dashboard.png`.
- Logo final: `assets/logo/` (Mix 1).
