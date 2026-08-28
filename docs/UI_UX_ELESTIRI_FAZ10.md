# PkgForge Desktop — UI/UX Eleştirisi ve Yaratıcı Öneriler (Faz 10)

> **Uygulama Durumu (Faz 10 — TAMAMLANDI):** Aşağıdaki tüm maddeler uygulanmış ve
> doğrulanmıştır. Kanıtlar: pnpm exec tsc -b (temiz), 166 vitest testi (41 dosya)
> geçti, cargo check temiz, tauri build --no-bundle başarılı, Python coverage %100
> korundu. 3.1 (aria-current) zaten mevcuttu; 3.3 (aria-label denetimi) doğrulandı.
> Yeni test dosyaları: ui/__tests__/{primitives,Dialog,Toast} + components/__tests__/
> {StatusPill,PathPicker,WhatsNew,SidecarGuard,FeatureTour,Onboarding,TopbarActions,
> Sidebar,DoctorPanel,WrappedDialog}. Test sayısı 128→166, dosya 28→41.

Faz 7'de 30, Faz 8'de 43, Faz 9'da 35 öneri uygulandı (bkz. ilgili belgeler).
Bu belge, projenin olgunlaştığı noktada kalan eleştirileri ve 2026 perspektifinden
yaratıcı önerileri kod referanslarıyla toplar. Model görüntü göremediği için her
madde kaynak koda dayanır. 2026-08.

Öncelik: [Y] Yüksek, [O] Orta, [D] Düşük

---

## 1. Test kapsamı — kalan boşluklar [O]

28 test dosyası / 128 test var ama 22 bileşen hâlâ testsiz. Faz 9'da eklenen
yeni bileşenler ve temel UI primitifleri öncelikli.

### 1.1 Faz 9 bileşenleri testsiz [O]
DoctorPanel ve WrappedDialog (Faz 9'da eklendi) için test yok.

### 1.2 Navigasyon bileşenleri testsiz [O]
Sidebar ve TopbarActions için test yok.

### 1.3 Dialog bileşenleri testsiz [O]
ConfirmDialog ve Dialog (odak tüpü, Escape, backdrop) için test yok.

### 1.4 Toast ve InfoTip testsiz [O]
Toast (aria-live, eylem butonu) ve InfoTip için test yok.

### 1.5 UI primitifleri testsiz [D]
Button, Badge, Input, Skeleton, ProgressBar için test yok.

### 1.6 Durum/yardımcı bileşenler testsiz [D]
StatusPill ve PathPicker için test yok.

### 1.7 Faz 8 bekçileri testsiz [D]
WhatsNew ve SidecarGuard için test yok.

### 1.8 Rehber bileşenleri testsiz [D]
FeatureTour ve Onboarding için test yok.

---

## 2. Backend/UI boşlukları [Y]

### 2.1 queue.cancel UI'da yok [Y]
core/api_server.py handle_queue_cancel çalışan batch pipeline'ları iptal eder
(item_id ile tekli veya tümü). Convert batch akışında çalışan bir öğeyi iptal
etmek için kullanılabilir (şu an sadece aktif pipeline.cancel var).

### 2.2 tools.status doctor ile örtük [D]
tools.status ayrı bir metod ama app.doctor zaten araç durumunu içerir
(DoctorPanel gösterir). api-types.ts otomatik üretildiği için elle temizlenmez;
bu madde belgeleme kararıdır (doctor yeterlidir).

---

## 3. Erişilebilirlik [O]

### 3.1 Sidebar aktif sayfa aria-current [O]
desktop/src/components/Sidebar.tsx aktif sayfa butonuna aria-current="page"
eklenmeli (ekran okuyucu konum bildirimi).

### 3.2 Installed filtre/sıralama memoize değil [O]
desktop/src/pages/Installed.tsx visible (filtre) ve sorted her render'da
yeniden hesaplanıyor; useMemo'a alınmalı (performans + erişilebilirlik tutarlılığı).

### 3.3 İkon-buton aria-label denetimi [D]
Tüm ikon-butonların aria-label taşıdığı doğrulanmalı (Faz 9'da büyük bölümü
eklendi; kalanlar taranmalı).

---

## 4. Performans [Y]

### 4.1 Sayfalar tembel yüklenmiyor [Y]
desktop/src/App.tsx 12 sayfayı statik import ediyor; React.lazy + Suspense ile
kod bölme yapılmalı, ilk yükleme küçültülmeli.

### 4.2 Saf görüntü bileşenleri memoize değil [O]
StatusPill, EmptyState gibi saf bileşenler React.memo ile sarılmalı.

### 4.3 Installed hesaplamaları memoize [O]
(3.2 ile aynı) visible/sorted useMemo.

---

## 5. UX — 2026 yaratıcı öneriler

### 5.1 Vurgu rengi kişiselleştirme [O]
Kullanıcı marka vurgu rengini seçebilsin (mavi/yeşil/mor/turuncu/gül); CSS
değişkeni olarak uygulanıp ayarlarda kalıcı olsun.

### 5.2 Wrapped ay-bazlı mini grafik [O]
WrappedDialog by_month verisini SVG mini bar grafik olarak göstersin
(yıllık ritim görselleşsin).

### 5.3 Geçmiş CSV dışa aktarma [O]
Installed tablosu CSV olarak indirilebilsin (analiz/raporlama için).

### 5.4 Komut paleti eşleşme vurgusu [O]
Palet arama eşleşen alt diziyi vurgulasın (fuzzy highlight).

### 5.5 Bildirim tercihi [O]
Masaüstü bildirimlerini aç/kapat ayarı (kalıcı); kapalıysa Rust bildirimleri
yine de OS düzeyinde çalışır ama UI bunu belgeler.

### 5.6 Sidebar son sayfalar [D]
Son gezilen 3 sayfa sidebar'da hızlı erişim olarak listelensin.

### 5.7 Rapor Markdown dışa aktar + kopyala [O]
Reports sistem sağlığı verisini Markdown olarak indir/kopyala (hata raporu için).

### 5.8 Alt+Ok sayfa geçmişi [D]
Alt+Sol/Sağ ile sayfalar arası ileri/geri gezinme (sayfa geçmişi yığını).

### 5.9 Palet: kurulu pakete atla [D]
Komut paletinde geçmişteki paket adları aranıp Installed sayfası o filtreyle açılsın.

### 5.10 Tanı kopyala (hata raporu) [O]
app.doctor + sürüm + platformu tek Markdown bloğu olarak panoya kopyalayan
"hata raporu için kopyala" eylemi (DoctorPanel'e buton).

---

## Öncelik Özeti

| # | Konu | Öncelik | Kategori |
|---|------|---------|----------|
| 1.1-1.8 | Test kapsamı (22 bileşen) | O/D | kalite |
| 2.1 | queue.cancel | Y | özellik |
| 2.2 | tools.status belgeleme | D | kalite |
| 3.1 | Sidebar aria-current | O | a11y |
| 3.2/4.3 | Installed memoize | O | perf |
| 3.3 | aria-label denetimi | D | a11y |
| 4.1 | Tembel yükleme | Y | perf |
| 4.2 | React.memo | O | perf |
| 5.1-5.10 | UX yaratıcı | O/D | UX |

---

## Önerilen Uygulama Sırası

Faz 10A (Performans — Yüksek): 4.1 tembel yükleme, 3.2/4.3 memoize, 4.2 React.memo.
Faz 10B (Özellik — Yüksek): 2.1 queue.cancel.
Faz 10C (UX yaratıcı): 5.1 vurgu rengi, 5.2 Wrapped grafik, 5.3 CSV, 5.4 fuzzy
   vurgu, 5.5 bildirim tercihi, 5.7 Markdown rapor, 5.10 tanı kopyala, 5.6 son
   sayfalar, 5.8 sayfa geçmişi, 5.9 pakete atla.
Faz 10D (Erişilebilirlik): 3.1 aria-current, 3.3 aria-label denetimi.
Faz 10E (Test kapsamı): 1.1-1.8 tüm testler.
