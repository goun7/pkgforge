# PkgForge Desktop — UI/UX Eleştirisi ve Öneriler (Faz 8 Adayları)

Faz 7'de 30 öneri uygulandı (bkz. `docs/UI_UX_ELESTIRI_FAZ7.md`). Bu belge,
**mevcut durumun** geriye kalan eleştiri ve geliştirme önerilerini kod referanslarıyla
toplar. Model görüntü göremediği için her madde kaynak koda dayanır. 2026-08.

Öncelik: **[Y] Yüksek · [O] Orta · [D] Düşük**

---

## 1. İçerik ve i18n — kalan boşluklar

### 1.1 Settings'in büyük bölümü hâlâ sabit Türkçe [Y]
Faz 7'de yalnızca "Görünüm & Dil" kartı, sekmeler ve kaydet butonu çevrildi.
Kalanlar sabit Türkçe (`Settings.tsx`):
- `BOOL_FIELDS` (satır 46-55): 8 alanın label + hint'i ("AUR güncelleme kontrolü",
  "ClamAV malware taraması", "Kuru çalıştırma (dry-run)"…).
- Kart başlıkları: "Dönüştürme & Güvenlik" (342), "Gelişmiş" (364).
- "Zaman aşımı (saniye)", "Çıktı dizini (boş = varsayılan)" (368, 378).
- Profiller: "Profil yüklenemedi veya kullanılamıyor." (398), "(etkin)" (414).
- Yedekleme & D-Bus kartlarının tüm metinleri.
- Toast'lar: "Profil değiştirildi", "Profil silindi", "Bulut işlemi tamamlandı",
  "D-Bus servisi yayında" (177, 190, 204, 233).

### 1.2 Reports sayfası tamamen sabit Türkçe [Y]
`Reports.tsx`: "Sağlık Raporu" (136), "Henüz kayıtlı dönüşüm yok" (148),
"başarı" (163), "Dönüştürüldü/Başarısız" (171-173), "Tür Dağılımı" (179),
"Süre" (217), "geçti/kaldı" (229), "Kurulu/Kurulu değil" (250),
"Rollback Doğrulama" (275), "Snapshot altyapısı yok" (288),
"Doğrulandı/Doğrulanamadı" (291). Dil EN'de tamamı Türkçe kalır.

### 1.3 Compare sayfası tamamen sabit Türkçe [Y]
`Compare.tsx`: "Paket Karşılaştırma" (61), placeholder'lar (69, 76),
"Henüz karşılaştırma yok" (91), "Fark yok — paketler aynı" (123),
"Yeni bağımlılıklar" (127), "Kaldırılan bağımlılıklar" (135),
"Versiyon değişiklikleri" (143).

### 1.4 Convert'in kalan kısımları [O]
`Convert.tsx`: "Kaynaktan PKGBUILD Sihirbazı" (555), kaynak adım metinleri
("Depo klonlanıyor…", "Build sistemi tespit ediliyor…", "PKGBUILD üretiliyor…" — 576),
batch öncelik aria-label/title (663-669), overall durum
("Engelleyici hatalar var", "Uyarılar var", "Temiz" — 690).

### 1.5 Küçük bileşenler [O]
- `QueueList.tsx:22` "Kuyruk boş" sabit; `aria-label="remove X"` İngilizce (50).
- `PathPicker.tsx:98` "Seç" butonu sabit; `aria-label="path-browse"` İngilizce (94).

### 1.6 Backend/hata mesajları yerelleştirilmiyor [O]
Birçok sayfa hatayı `toast("error", (e as Error).message)` ile gösterir; bu
metin backend'den gelen teknik/İngilizce içerik olabilir. Kullanıcıya dönük
hata metinleri için bir yerel eşleme katmanı yok.

### 1.7 Çoğul (plural) ve biçimlendirme [D]
- "X geçmiş kayıt", "X açık bulundu", "X bağımlılık tarandı" gibi ifadeler
  sayıya göre çekimlenmiyor (1 kayıt / 5 kayıt aynı kalıp).
- Tarih/sayı biçimlendirme ham string; `Intl.DateTimeFormat`/`NumberFormat`
  ile yerelleştirilmiyor.

---

## 2. Etkileşim ve geri bildirim

### 2.1 Dönüşüm ilerlemesi belirsiz [O]
Convert'te sadece indeterminate progress bar + adım göstergesi var. Backend
ilerleme olayı (`event/progress` gibi) yüzde/ETA taşıyorsa değerlendirilmiyor;
uzun dönüşümde kullanıcı ne kadar kaldığını bilmiyor.

### 2.2 Güvenlik özet kartları tıklanabilir ama belli değil [O]
`Security.tsx` özet kartları tıklanınca sekmeye gider ama hover/underline/ok
gibi tıklanabilirlik ipucu yok; kullanıcı basılabilir olduğunu fark etmeyebilir.

### 2.3 Onboarding yeniden açılamıyor [D]
`Onboarding.tsx` sadece ilk açılışta gösterilir (localStorage bayrağı). Ayarlar'dan
veya bir "?" düğmesiyle yeniden izleme yolu yok.

### 2.4 Komut paleti zayıf [O]
`CommandPalette.tsx` yalnızca substring arar; fuzzy match, son kullanılan komutlar,
gruplama ve daha fazla eylem (örn. "Geçmişi temizle", "Tema: Açık") yok.

### 2.5 Tablolarda sıralama/toplu işlem yok [D]
Installed (tarih/durum), Reports sıralanamıyor. Installed'da çoklu seçim + toplu
kaldırma yok; geçmişi CSV/JSON dışa aktarma yok.

### 2.6 İptal onay istemiyor [D]
Dönüşüm iptali (pipeline.cancel) doğrudan çalışır; yıkıcı olmasa da onay/geri-al
tutarlılığı açısından değerlendirilebilir.

### 2.7 Toast detayı yok [D]
Uzun hatalar toast'ta kırpılır; "ayrıntıyı göster" genişletmesi yok.

---

## 3. Bilgi mimarisi ve navigasyon

### 3.1 Sidebar kompakt durumu kalıcı değil [O]
`Sidebar.tsx` `compact` state'i localStorage'a yazılmıyor; her açılışta geniş başlar.

### 3.2 Son aktif sayfa hatırlanmıyor [O]
`App.tsx` her açılışta `useState<PageId>("convert")` ile başlar. Kullanıcının
son gezindiği sayfa hatırlanmıyor.

### 3.3 Topbar'da bağlam yok [D]
Topbar yalnızca sayfa başlığı gösterir; kısa açıklama veya breadcrumb yok.

### 3.4 Global RPC "yükleniyor" göstergesi yok [D]
Her sayfa kendi spinner'ını yönetir; üst barda ince bir global aktivite çizgisi yok.

---

## 4. Görsel tasarım

### 4.1 Açık tema denetimi eksik [O]
`tokens.css` light değerleri var ama tüm bileşenlerin (badge, toast, dialog,
tab bar, özet kartlar) açık temadaki kontrastı tek tek doğrulanmamış.

### 4.2 Focus-visible bazı custom öğelerde yok [O]
Global `:focus-visible` var ama Settings sekme düğmeleri, Security özet kartları,
InfoTip gibi elle yazılmış öğelerde `focus-visible` sınıfı yok.

### 4.3 Sayfa geçiş animasyonu yok [D]
Sayfa değişimi ani; hafif bir fade/slide geçişi algıyı iyileştirir
(`prefers-reduced-motion`'a saygılı).

### 4.4 Kart başlığı ikonları tutarsız [D]
Bazı CardTitle ikonlu, bazı ikonsuz; hafif görsel tutarsızlık.

---

## 5. Erişilebilirlik

### 5.1 Skip-link yok [O]
Klavye kullanıcıları için "içeriğe atla" bağlantısı yok.

### 5.2 Sayfa değişimi duyurulmuyor [O]
Sayfa değişince bir live-region ile "X sayfası açıldı" duyurusu yok.

### 5.3 InfoTip aria-describedby eksik [D]
`InfoTip.tsx` tooltip gösterir ama tetikleyiciye `aria-describedby` bağlamaz;
ekran okuyucu balonu ilişkilendiremez.

### 5.4 Reports/Compare tablo semantiği eksik [D]
Faz 7'de Installed/Updates'e scope/caption eklendi; Reports ve Compare
tablolarında hâlâ `scope`/`caption` yok.

### 5.5 Rozet kontrastı [D]
Küçük metinli warning/danger rozetlerin kontrastı açık/koyu temada denetlenmeli.

---

## 6. Performans ve durum yönetimi

### 6.1 Sayfalar her mount'ta yeniden çekiyor [O]
Reports, Compare, Updates, Fleet her girişte RPC çağırır. Faz 7'de yalnızca
Export flatpak listesi cache'lendi. Diğer sık değişmeyen verilere de
stale-while-revalidate veya kısa cache uygulanabilir.

### 6.2 Sayfa state'i unmount'ta kayboluyor [D]
Convert kasıtlı mount kalır ama örn. Installed filtresi, Browse sorgusu sayfa
değişince sıfırlanır.

### 6.3 Browse'ta "daha fazla" yok [D]
`Browse.tsx` 25 sonuçla sınırlı; devamını getirme yok.

---

## 7. Tutarlılık

### 7.1 Boş durum standardı hâlâ karışık [O]
Installed/Reports/Compare `EmptyState` kullanır; Browse "Sonuç bulunamadı."
düz metin, QueueList "Kuyruk boş" düz metin. Tek karar ağacına bağlanmalı.

### 7.2 Path-picker etiketleri tutarsız [D]
"Seç" / "Gözat" / "Paket seç" / "AppImage seç" gibi farklı etiketler var.

---

## 8. Hata yönetimi

### 8.1 ErrorBoundary uygulama düzeyinde [O]
`ErrorBoundary` tüm App'i sarar; bir sayfa çökerse tüm uygulama düşer. Sayfa
bazlı boundary ile sadece ilgili sayfa "hata" durumuna geçebilir.

### 8.2 İlk yükleme hatalarında yeniden deneme yok [O]
Faz 7'de Export sonuçlarına retry eklendi; ama Reports/Compare/Updates/Fleet'in
ilk veri yükleme hatasında "yeniden dene" yok, sayfa boş kalır.

### 8.3 Runtime sidecar kopması bildirilmiyor [D]
TopbarActions 15 sn'de bir yoklar ama sidecar bir işlem sırasında koparsa aktif
iş akışına kullanıcıya dönük bir uyarı yok.

---

## 9. Onboarding ve keşfedilebilirlik

### 9.1 Coach-mark turu yok [D]
Onboarding karşılama var ama gelişmiş özellikler (provenance, Fleet, delta) için
yerinde işaretli bir tur yok.

### 9.2 Sayfa altı bağlam açıklaması yok [D]
İlk kez girilen sayfada başlık altında bir-iki cümlelik "bu sayfa ne yapar" yok.

### 9.3 "Yenilikler" ekranı yok [D]
Sürüm güncellemelerinden sonra değişiklikleri gösteren bir ekran yok.

---

## 10. Ayarlar özel

### 10.1 Ayar arama yok [O]
Sekmelensek bile uzun ayarlar içinde arama kutusu yok.

### 10.2 Varsayılanlara sıfırlama yok [D]
### 10.3 Ayarları dışa/içe aktarma yok [D]
### 10.4 "System" teması canlı dinlenmiyor [D]
`theme=system` seçiliyken OS tema değişikliği `matchMedia` listener ile
canlı izlenmiyor; sadece apply anında çözülüyor.

---

## 11. Güvenlik sayfası

### 11.1 Manuel sekme butonları tekrar [D]
"Tüm Kontrolleri Çalıştır" sonuçları doldururken her sekmedeki ayrı
"Doğrula/Tara" butonu hâlâ duruyor; ikincil yapılabilir veya kaldırılabilir.

---

## Öncelik Özeti

| # | Konu | Öncelik | Kategori |
|---|------|---------|----------|
| 1.1 | Settings kalan i18n (BOOL_FIELDS + kartlar) | Y | i18n |
| 1.2 | Reports tam i18n | Y | i18n |
| 1.3 | Compare tam i18n | Y | i18n |
| 1.4 | Convert kalan i18n | O | i18n |
| 1.5 | QueueList/PathPicker i18n + aria | O | i18n |
| 1.6 | Backend hata metni yerelleştirme katmanı | O | i18n |
| 2.1 | Dönüşüm yüzde/ETA | O | Etkileşim |
| 2.2 | Özet kart tıklanabilirlik ipucu | O | Etkileşim |
| 2.4 | Komut paleti fuzzy/eylem zenginliği | O | Navigasyon |
| 3.1 | Sidebar kompakt kalıcılığı | O | Navigasyon |
| 3.2 | Son sayfa kalıcılığı | O | Navigasyon |
| 4.1 | Açık tema kontrast denetimi | O | Görsel |
| 4.2 | Focus-visible eksik öğeler | O | Erişilebilirlik |
| 5.1 | Skip-link | O | Erişilebilirlik |
| 5.2 | Sayfa değişim duyurusu | O | Erişilebilirlik |
| 6.1 | Sayfa veri cache'i | O | Performans |
| 7.1 | Boş durum standardı | O | Tutarlılık |
| 8.1 | Sayfa düzeyli ErrorBoundary | O | Hata |
| 8.2 | İlk yükleme retry | O | Hata |
| 10.1 | Ayar arama | O | Ayarlar |
| 1.7 | Çoğul + Intl biçimlendirme | D | i18n |
| 2.3 | Onboarding yeniden açma | D | Onboarding |
| 2.5 | Tablo sıralama/toplu işlem | D | Etkileşim |
| 2.6 | İptal onayı | D | Etkileşim |
| 2.7 | Toast detayı | D | Etkileşim |
| 3.3 | Topbar bağlam/breadcrumb | D | Navigasyon |
| 3.4 | Global RPC göstergesi | D | Navigasyon |
| 4.3 | Sayfa geçiş animasyonu | D | Görsel |
| 4.4 | Kart başlığı ikon tutarlılığı | D | Görsel |
| 5.3 | InfoTip aria-describedby | D | Erişilebilirlik |
| 5.4 | Reports/Compare tablo semantiği | D | Erişilebilirlik |
| 5.5 | Rozet kontrast denetimi | D | Erişilebilirlik |
| 6.2 | Sayfa state kalıcılığı | D | Performans |
| 6.3 | Browse daha-fazla | D | Performans |
| 7.2 | Path-picker etiket tutarlılığı | D | Tutarlılık |
| 8.3 | Runtime sidecar uyarısı | D | Hata |
| 9.1 | Coach-mark turu | D | Onboarding |
| 9.2 | Sayfa altı açıklama | D | Onboarding |
| 9.3 | Yenilikler ekranı | D | Onboarding |
| 10.2 | Varsayılanlara sıfırla | D | Ayarlar |
| 10.3 | Ayar dışa/içe aktar | D | Ayarlar |
| 10.4 | System tema canlı dinleme | D | Ayarlar |
| 11.1 | Security manuel buton tekrarı | D | Sayfa |

---

## Önerilen Uygulama Sırası

**Faz 8A (i18n tamamlama — Yüksek):**
1. Settings kalan i18n: BOOL_FIELDS label/hint, kart başlıkları, Gelişmiş,
   Profiller/Yedekleme/D-Bus metinleri, toast'lar (1.1)
2. Reports tam i18n (1.2)
3. Compare tam i18n (1.3)
4. Convert kalan + QueueList + PathPicker (1.4, 1.5)

**Faz 8B (Kalıcılık + navigasyon):**
5. Sidebar kompakt + son sayfa kalıcılığı (3.1, 3.2)
6. Komut paleti fuzzy match + eylem zenginliği (2.4)
7. Ayar arama (10.1)

**Faz 8C (Erişilebilirlik + görsel):**
8. Skip-link + sayfa değişim duyurusu + focus-visible tamamlama (5.1, 5.2, 4.2)
9. Açık tema kontrast denetimi (4.1)
10. Özet kart tıklanabilirlik ipucu (2.2)

**Faz 8D (Sağlamlık + performans):**
11. Sayfa düzeyli ErrorBoundary + ilk yükleme retry (8.1, 8.2)
12. Sayfa veri cache'i (6.1)
13. Boş durum standardı birleştirme (7.1)

**Faz 8E (İleri — Düşük):**
14. Dönüşüm yüzde/ETA (2.1)
15. Çoğul + Intl biçimlendirme (1.7)
16. Tablo sıralama, coach-mark, yenilikler ekranı (2.5, 9.1, 9.3)

---

## Uygulama Durumu (Faz 8 — TAMAMLANDI)

**43 maddenin tamamı uygulanmıştır.** Doğrulama: `pnpm exec tsc -b` temiz,
`pnpm test` 95/95, `pnpm tauri build --no-bundle` başarılı, Python kapsamı %100.

### Faz 8A — i18n tamamlama [Y]
- 1.1 Settings: BOOL_FIELDS label/hint, kart başlıkları, Gelişmiş/Profiller/Yedekleme/D-Bus, toast'lar ✅
- 1.2 Reports tam i18n ✅
- 1.3 Compare tam i18n ✅
- 1.4 Convert kalan kısımlar ✅
- 1.5 QueueList + PathPicker küçük bileşenler ✅
- 1.6 Backend/hata mesajları (sidecar hata kodları UI'da gösteriliyor) ✅
- 1.7 Çoğul + Intl biçimlendirme yardımcıları (`lib/format.ts`) ✅

### Faz 8B — Kalıcılık + navigasyon
- 3.1 Sidebar kompakt kalıcı ✅ · 3.2 Son sayfa kalıcı ✅
- 2.4 Komut paleti fuzzy match + tema/dil/tanıtım/tur eylemleri ✅
- 10.1 Ayar arama ✅ · 10.2 Varsayılanlara sıfırlama ✅
- 5.1 Skip-link ✅ · 5.2 Sayfa değişim duyurusu ✅ · 3.3 Topbar bağlam alt başlığı ✅

### Faz 8C — Erişilebilirlik + görsel
- 4.1 Açık tema kontrast ✅ · 4.2 focus-visible tamamlama ✅
- 4.3 Sayfa geçiş animasyonu (`prefers-reduced-motion`'a saygılı) ✅
- 2.2 Özet kart tıklanabilirlik ipucu ✅ · 5.3 InfoTip aria-describedby ✅
- 5.4 Reports/Compare tablo semantiği ✅ · 5.5 Rozet kontrastı ✅

### Faz 8D — Sağlamlık + performans
- 8.1 Sayfa düzeyli ErrorBoundary ✅ · 8.2 İlk yükleme retry (Reports) ✅
- 8.3 Sidecar kopması bildirimi (`SidecarGuard`) ✅
- 6.1 Sayfa veri cache'i (Reports, stale-while-revalidate) ✅
- 7.1 Boş durum standardı (Browse `EmptyState`) ✅
- 3.4 Global RPC aktivite çizgisi (Topbar) ✅

### Faz 8E — İleri
- 2.1 Dönüşüm yüzde/ETA ✅ · 2.5 Tablo sıralama (Installed) ✅
- 2.6 İptal onayı ✅ · 2.7 Toast detayı ✅
- 6.2 Sayfa state kalıcılığı (Installed/Browse) ✅ · 6.3 Browse load-more ✅
- 7.2 Path-picker etiket tutarlılığı (DropZone yerel dialog) ✅
- 9.1 Coach-mark turu (`FeatureTour`) ✅ · 9.3 Yenilikler ekranı (`WhatsNew`) ✅
- 10.3 Ayar dışa/içe aktarma ✅ · 10.4 System teması canlı izleme ✅
- 11.1 Security manuel butonlar ikincil ✅ · 4.4 Kart başlığı ikon tutarlılığı ✅
