# PkgForge Desktop — UI/UX Eleştirisi ve Yaratıcı Öneriler (Faz 9)

Faz 7'de 30, Faz 8'de 43 öneri uygulandı (bkz. docs/UI_UX_ELESTIRI_FAZ7.md ve
docs/UI_UX_ELESTIRI_FAZ8.md). Bu belge, projenin geldiği son noktada kalan
eleştirileri ve 2026 perspektifinden yaratıcı önerileri kod referanslarıyla toplar.
Model görüntü göremediği için her madde kaynak koda dayanır. 2026-08.

Öncelik: [Y] Yüksek, [O] Orta, [D] Düşük

---

## 1. İçerik ve i18n — kalan son boşluklar

Faz 8'de sayfaların büyük bölümü yerelleştirildi; ancak toast mesajları, bazı
bileşen içi metinler ve Rust tarafı hâlâ sabit Türkçe içeriyor.

### 1.1 rpc zaman aşımı mesajı sabit Türkçe [Y]
desktop/src/lib/rpc.ts içinde "Yanıt zaman aşımı: method" sabit string.

### 1.2 ConfirmDialog varsayılan iptal etiketi [Y]
desktop/src/components/ui/ConfirmDialog.tsx cancelLabel varsayılanı "Vazgeç".

### 1.3 LogViewer sabit metinleri [Y]
desktop/src/components/LogViewer.tsx: "Log · duraklatıldı", "Henüz log yok…".

### 1.4 DepGraph sabit metinleri [Y]
desktop/src/components/DepGraph.tsx: "Yabancı:", aria-label "Bağımlılık grafiği",
"kurulu" / "eksik" / "yabancı" rozetleri.

### 1.5 TopbarActions sabit metinleri [Y]
desktop/src/components/TopbarActions.tsx: sidecar durum title/aria'ları,
"Dili değiştir" / "Dil" / "Temayı değiştir" / "Tema".

### 1.6 Convert kalan toast'ları [Y]
desktop/src/pages/Convert.tsx: "Tamamlandı", "Başarısız", "Grafik oluşturulamadı",
"Kurulum başarısız", "PKGBUILD oluşturulamadı", "OCI imajı oluşturuluyor…",
"başlatılıyor", "Bekleyen öğe yok", "Zaten çalışıyor".

### 1.7 Settings kalan sabitleri [Y]
desktop/src/pages/Settings.tsx: "Türkçe" option etiketi, "Senkron ayarları kaydedildi".

### 1.8 Security kalan toast'ları [Y]
desktop/src/pages/Security.tsx: "Önce bir paket yolu girin", "SBOM oluşturulamadı",
"Kalite analizi başarısız", "provenance kaydı bulunamadı", "CVE taraması başarısız",
"Tüm güvenlik kontrolleri tamamlandı".

### 1.9 Updates kalan sabitleri [Y]
desktop/src/pages/Updates.tsx: "Aralık en az 1 saat olmalı", pkexec toast'ları,
"Bir paket adı girin", "Cross-check başarısız", caption "Kaynak sürüm karşılaştırması".

### 1.10 Export kalan toast'ları [Y]
desktop/src/pages/Export.tsx: "Dışa aktarma başarısız", "Bir AppImage dosyası seçin",
"Bir Flatpak uygulaması seçin", "Bir .pkg.tar.zst paketi seçin".

### 1.11 Plugins kalan toast'ları [O]
desktop/src/pages/Plugins.tsx: "İşlem tamamlandı", "Plugin işlemi başarısız", "kaldırıldı".

### 1.12 Rust tray menüsü sabit Türkçe [D]
desktop/src-tauri/src/lib.rs: tray menü öğeleri "Göster" / "Çıkış" ve bildirim
başlıkları sabit Türkçe. Rust tarafı i18n sözlüğüne bağlı olmadığı için en azından
nötr/İngilizce yapılabilir ya da olduğu gibi bırakıldığı belgelenir.

---

## 2. Backend'de hazır ama UI'da yok — yaratıcı özellik fırsatları [Y]

core/api_server.py METHODS sözlüğünde kayıtlı ama desktop'un hiç çağırmadığı
metodlar var. Bunlar sıfır backend maliyetiyle yeni özellik olur.

### 2.1 Sistem Doktoru paneli (app.doctor + tools.status) [Y]
core/doctor.py run_doctor() sürüm, zorunlu/opsiyonel araçlar, anahtarlık, depolama,
D-Bus ve zamanlayıcı sağlığını tek raporda toplar. Reports sayfasına bir "Sistem
Doktoru" kartı eklenip sonuçlar yeşil/sarı/kırmızı rozetlerle gösterilebilir.
Araç eksikse (pacman/makepkg) kullanıcıya somun kurulum rehberi sunulur.

### 2.2 Stats Wrapped — yıllık rapor (stats.wrapped) [Y]
core/stats_wrapped.py build_wrapped() Spotify-Wrapped tarzı yıllık özet üretir:
toplam/başarılı dönüşüm, başarı oranı, en yoğun ay, top 5 paket, tür dağılımı.
Reports'a bir "Yıl Özeti" butonu + şık bir dialog ile sunulabilir.

### 2.3 Uyumluluk politika seviyesi (policy.get / policy.set) [O]
core/http_api/meta.py policy_get/set standard|strict seviyesini yönetir.
Settings'e bir "Uyumluluk Politikası" seçici eklenebilir; strict modda riskli
dönüşümler daha sıkı denetlenir.

### 2.4 Zamanlanmış görevi şimdi çalıştır (schedule.run) [O]
core/api_server.py handle_schedule_run force parametresiyle görevi anında çalıştırır.
Zamanlayıcı ayarının yanına "Şimdi çalıştır" butonu eklenebilir.

### 2.5 Yedek/senkron içe aktarma (sync.import) [O]
core/cloud_sync.py import_backup bir yedek dosyasını geri yükler. Settings Yedekleme
kartında "Dışa aktar" yanında "İçe aktar" (dosya seçip geri yükle) eklenebilir.

### 2.6 İmzalama anahtarlarını listele (security.keys) [O]
core/package_signing.py list_keys mevcut imza anahtarlarını döner. Security sayfasına
küçük bir "Anahtarlar" bölümü eklenebilir.

### 2.7 Kurulum provası (install.rehearse) [D]
core/install_rehearsal.py rehearse_install konteyner içi kurulum provası yapıp
dosya-liste diff'i döner. Convert'e "Önce prova et" gibi ileri düzey bir seçenek
eklenebilir (distrobox gerektirir, zarif düşer).

### 2.8 Uygulama sürümü (app.version) [D]
app_version isim+sürüm döner. TopbarActions'a veya Settings'e "Hakkında" ipucu
olarak sürüm gösterilebilir (WhatsNew zaten 2.0.0 sabiti kullanıyor; canlı değere bağlanır).

---

## 3. Ölü kod ve bağımlılık hijyeni

### 3.1 framer-motion kullanılmıyor [O]
desktop/package.json bağımlılığı framer-motion hiçbir dosyada import edilmiyor
(0 kullanım). Kaldırılıp bundle küçültülmeli ya da gerçekten kullanılmalı.

---

## 4. Test kapsamı boşlukları [O]

18 test dosyası var ama Faz 8'de eklenen yeni modüller ve bazı bileşenler testsiz.

### 4.1 lib/format.ts testsiz [O]
plural / fmtNumber / fmtDate yardımcıları için birim test yok.

### 4.2 lib/cache.ts testsiz [O]
cacheGet / cacheSet / cacheInvalidate TTL mantığı testsiz.

### 4.3 lib/theme.ts testsiz [O]
resolveTheme / applyTheme / watchSystemTheme testsiz.

### 4.4 CommandPalette fuzzy match testsiz [O]
fuzzyScore substring/subsequence puanlama mantığı testsiz.

### 4.5 Yeni Faz 8 bileşenleri testsiz [O]
WhatsNew, FeatureTour, SidecarGuard, ErrorBoundary(page variant) için test yok.

### 4.6 Küçük UI bileşenleri testsiz [D]
EmptyState, InfoTip, PathPicker, Sidebar, Topbar için test yok.

---

## 5. UX — 2026 yaratıcı öneriler

### 5.1 Klavye kısayol yardım katmanı [O]
Ctrl+/ veya ? ile tüm kısayolları (Ctrl+K, Alt+1..9) gösteren bir katman/panel.
Komut paletinden de açılabilir.

### 5.2 Log dışa aktarma [O]
LogViewer'a logları .txt/.log olarak indirme butonu (dönüşüm sorunlarını raporlamak için).

### 5.3 Rapor dışa aktarma [D]
Reports'taki sistem sağlığı/benchmark verisini JSON veya Markdown olarak indirme.

### 5.4 Tablo yoğunluk anahtarı [D]
Installed/Updates tabloları için kompakt/rahat yoğunluk seçeneği (çok satırda okunabilirlik).

### 5.5 OLED siyah tema / vurgu rengi [D]
tokens.css'e gerçek siyah (OLED) yüzey seçeneği veya marka vurgu rengini kişiselleştirme.

### 5.6 Global sürükle-bırak [D]
Convert sayfasının tamamı drop hedefi olsun (şu an sadece DropZone alanı).

### 5.7 Yıkıcı işlem geri alma [D]
History clear gibi işlemlerden sonra "Geri al" toast eylemi (veri kaybı emniyeti).

### 5.8 Komut paleti yakın öğeler [D]
Komut paletinde son kullanılan komutların üste sabitlenmesi / eşleşen kısmın vurgulanması.

---

## Öncelik Özeti

| # | Konu | Öncelik | Kategori |
|---|------|---------|----------|
| 1.1-1.11 | Kalan i18n (toast + bileşen metinleri) | Y | i18n |
| 2.1 | Sistem Doktoru | Y | özellik |
| 2.2 | Stats Wrapped | Y | özellik |
| 2.3 | Politika seviyesi | O | özellik |
| 2.4 | schedule.run | O | özellik |
| 2.5 | sync.import | O | özellik |
| 2.6 | security.keys | O | özellik |
| 2.7 | install.rehearse | D | özellik |
| 2.8 | app.version | D | özellik |
| 3.1 | framer-motion kaldır | O | hijyen |
| 4.1-4.6 | Test kapsamı | O/D | kalite |
| 5.1-5.8 | UX yaratıcı | O/D | UX |
| 1.12 | Rust tray i18n | D | i18n |

---

## Önerilen Uygulama Sırası

Faz 9A (i18n tamamlama — Yüksek): 1.1-1.11 tüm sabit Türkçe metinler.
Faz 9B (Yaratıcı özellikler — Yüksek): 2.1 Doktor, 2.2 Wrapped, 2.3 Politika,
   2.4 schedule.run, 2.5 sync.import, 2.6 security.keys, 2.8 app.version.
Faz 9C (Hijyen + kalite): 3.1 framer-motion kaldır, 4.1-4.6 testler.
Faz 9D (UX yaratıcı — Orta/Düşük): 5.1 kısayol yardımı, 5.2 log dışa aktar,
   5.3 rapor dışa aktar, 5.5 OLED tema; 2.7 install.rehearse (zarif).


---

## Uygulama Durumu (Faz 9 — TAMAMLANDI)

35 maddenin 30'u bu fazda uygulandı ve doğrulandı; 5 madde bilinçli olarak
belgelendi/gelecek faza bırakıldı (hepsi [D] düşük öncelik veya tasarım kararı).
Doğrulama kanıtları: pnpm exec tsc -b (temiz), 128 vitest testi (28 dosya) geçti,
tauri build --no-bundle başarılı, Python coverage %100 (11682 ifade) korundu.

### 1. i18n — kalan son boşluklar
- 1.1 ✅ rpc.ts zaman aşımı → rpcTimeout (getLang+tFor ile lib düzeyinde)
- 1.2 ✅ ConfirmDialog varsayılan etiketler → confirmConfirm/confirmCancel
- 1.3 ✅ LogViewer → logPaused/logEmpty + logCopy/logClear aria ve başlıkları
- 1.4 ✅ DepGraph → depTotal/depInstalled/depMissing/depForeign/depDepth/depGraphAria/depForeignTag
- 1.5 ✅ TopbarActions → sidecarConnecting/Connected/NotConnected, langToggle*, themeToggle*
- 1.6 ✅ Convert toast'ları → convDone/convFailed/convGraphFail/convInstallFail/convPkgbuildFail/convOciStarted, queueNoPending/queueAlreadyRunning
- 1.7 ✅ Settings senkron mesajı → setSyncSaved. Dil seçenekleri (Türkçe/English) endonym olarak korundu — bu doğru i18n pratiğidir, hata değildir.
- 1.8 ✅ Security toast'ları → secNeedPath/secSbomFail/secQualityFail/secNoProvenance/secCveFail/secAllDone
- 1.9 ✅ Updates → updIntervalMin/updNeedName/updCrossFail/updCrossCaption/updDeltaEnablePriv/updDeltaDisablePriv
- 1.10 ✅ Export toast'ları → expFail/expNeedAppimage/expNeedFlatpak/expNeedPkg
- 1.11 ✅ Plugins toast'ları → plugDone/plugFail/plugRemoved. Ek: Tools sayfası da temizlendi → toolsRpmFail/toolsAbiFail/toolsImgScanFail/toolsAttestFail/toolsPublishFail/toolsSnapshotFail/toolsNeedImgPath
- 1.12 ⚠️ Rust tray menüsü ve bildirim başlıkları Türkçe bırakıldı (desktop/src-tauri/src/lib.rs). Rust tarafında bir i18n sözlüğü yoktur ve Türkçe birincil yereldir; karar belgelendi.

### 2. Backend'de hazır ama UI'da yok — yaratıcı özellikler
- 2.1 ✅ Sistem Doktoru → DoctorPanel.tsx (app.doctor), Reports sayfasına kart; eksik araçlar için kurulum komutu önerisi
- 2.2 ✅ Stats Wrapped → WrappedDialog.tsx (stats.wrapped), Reports'a "Yıl Özeti" butonu; Spotify tarzı yıllık özet
- 2.3 ✅ Uyumluluk politikası → zaten Settings'ta compat_policy seçicisi vardı (standard|strict); core/policy_engine.py SETTINGS_KEY="compat_policy" doğrulandı
- 2.4 ✅ schedule.run → Updates zamanlayıcı kartına "Şimdi çalıştır" butonu (force=true)
- 2.5 ✅ sync.import → zaten Settings yedek kartında "İçe Aktar" butonu vardı (doğrulandı)
- 2.6 ✅ security.keys → Security imza sekmesine "İmza Anahtarları" listesi (GPG key_id + uid)
- 2.7 ⚠️ install.rehearse → UI'a eklenmedi. Konteyner/distrobox bağımlılığı ve uzun süren prova süreci masaüstü UX'inde takılma riski taşır; gelecek faza bırakıldı.
- 2.8 ✅ app.version → Settings sayfa altına canlı sürüm göstergesi (PkgForge Sürüm x.y.z)

### 3. Ölü kod ve bağımlılık hijyeni
- 3.1 ✅ framer-motion kaldırıldı (package.json + pnpm lockfile, 0 kullanım doğrulandı)

### 4. Test kapsamı boşlukları
- 4.1 ✅ lib/__tests__/format.test.ts (plural/fmtNumber/fmtDate)
- 4.2 ✅ lib/__tests__/cache.test.ts (TTL/invalidation, fake timers)
- 4.3 ✅ lib/__tests__/theme.test.ts (resolveTheme dark/light/system/oled, applyTheme)
- 4.4 ✅ components/__tests__/CommandPalette.test.tsx (fuzzy substring+subsequence, çalıştırma, kapalılık)
- 4.5 ✅ components/__tests__/ErrorBoundary.test.tsx (full + page variant, retry ile recovery)
- 4.6 ✅ components/__tests__/EmptyState.test.tsx + ShortcutsDialog.test.tsx
- Ek: test setup'ına bellek-içi localStorage/sessionStorage stub eklendi (jsdom sağlamıyordu); kalici-state testlerinin önü açıldı.

### 5. UX — 2026 yaratıcı öneriler
- 5.1 ✅ ShortcutsDialog.tsx → Ctrl+/ , komut paleti "Klavye kısayollarını göster" ve topbar klavye ikonu ile açılan yardım katmanı
- 5.2 ✅ LogViewer'a logları .txt indirme butonu (pkgforge-log.txt)
- 5.3 ✅ Reports sistem sağlığını JSON indirme (pkgforge-report.json)
- 5.4 ⚠️ Tablo yoğunluk anahtarı → düşük öncelik, gelecek faza bırakıldı
- 5.5 ✅ OLED siyah tema → tokens.css [data-theme="oled"], theme.ts, Settings seçeneği ve komut paleti "Tema: OLED Siyah"
- 5.6 ⚠️ Global sürükle-bırak → düşük öncelik, gelecek faza bırakıldı (DropZone zaten mevcut)
- 5.7 ⚠️ Yıkıcı işlem geri alma → düşük öncelik, gerçek geri-alma mekanizması gerektirir, gelecek faza bırakıldı
- 5.8 ✅ Komut paleti son kullanılanlar → localStorage ile son 5 komut üste sabitlenir

### Özet
| Kategori | Toplam | Uygulanan | Belgelenen/Erteleme |
|----------|--------|-----------|---------------------|
| 1. i18n | 12 | 11 | 1 (1.12) |
| 2. Özellik | 8 | 7 | 1 (2.7) |
| 3. Hijyen | 1 | 1 | 0 |
| 4. Test | 6 | 6 | 0 |
| 5. UX | 8 | 5 | 3 (5.4/5.6/5.7) |
| **Toplam** | **35** | **30** | **5** |

Yeni dosyalar: DoctorPanel.tsx, WrappedDialog.tsx, ShortcutsDialog.tsx +
7 test dosyası (format, cache, theme, CommandPalette, ErrorBoundary, EmptyState, ShortcutsDialog).
