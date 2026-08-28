# PkgForge Desktop — UI/UX Değerlendirmesi

Bu belge Tauri + React masaüstü arayüzünün güçlü yönlerini, eleştirileri ve
önceliklendirilmiş iyileştirme önerilerini içerir. 2026-08 değerlendirmesi.

---

## Güçlü yönler

- Koyu tema, kart tabanlı modern ve tutarlı görsel dil.
- Özellik seti çok zengin: güvenlik (imza/SBOM/CVE/provenance/Sigstore),
  uyumluluk notu, filo konsolu, denetim izi, attestasyon, AUR taraması.
- StepIndicator, LogViewer, DropZone, QueueList gibi iyi soyutlanmış bileşenler.
- Olay tabanlı (event) geri bildirim mimarisi uzun işler için doğru seçim.

---

## Eleştiriler ve öneriler

### 1. Navigasyon çok kalabalık — ÖNCELİK: YÜKSEK
Sidebar'da 12 üst düzey sayfa var (Dönüştür, Kurulanlar, AUR Gözat,
Güncellemeler, Güvenlik, Raporlar, Dışa Aktar, Karşılaştır, Eklentiler,
Araçlar, Fleet, Ayarlar). Bilişsel yük yüksek; yeni kullanıcı şaşırır.

Öneri: Sayfaları mantıksal gruplara ayır veya niş olanları katla:
- Dönüştür (çekirdek): Dönüştür / Kaynaktan / Toplu (zaten sekme).
- Kütüphane: Kurulanlar, Raporlar.
- Keşfet: AUR Gözat, Güncellemeler.
- Güvenlik ve Kalite: Güvenlik, Karşılaştır.
- Sistem (katlanabilir): Araçlar, Dışa Aktar, Eklentiler, Fleet, Ayarlar.

### 2. Dönüşüm ilerlemesi takılmış hissi veriyor — ÖNCELİK: YÜKSEK
İlerleme çubuğu makepkg boyunca 40 ile 65 arasında sabit kalıyor; büyük
paketlerde bu dakikalar sürebilir ve uygulama donmuş gibi görünür. (Arka planda
dönüşüm zaten optimize: çok iş parçacıklı zstd -T0 -9 ve !strip; yavaşlık
paket boyutundan kaynaklanıyor.)

Öneri:
- Dönüşüm adımında geçen süre sayacı göster.
- makepkg çıktısını log panelinde daha belirgin akıt.
- Sabit yüzde yerine belirsiz (indeterminate) çizgi animasyonu + adım adı.

### 3. Kritik sonuçlar toast ile kayboluyor — ÖNCELİK: YÜKSEK
Dönüşüm başarısı/başarısızlığı, kurulum sonucu gibi önemli çıktılar geçici
toast'larda gösterilip kayboluyor. Kullanıcı sonucu kaçırabilir.

Öneri: Dönüşüm bitince kalıcı bir sonuç bandı göster: paket adı, çıktı yolu,
durum rozeti ve Klasörü Aç / Yolu Kopyala / Kur butonları.

### 4. Boş durumlar zayıf — ÖNCELİK: ORTA
Birçok sayfa (Kurulanlar, Raporlar, Karşılaştır) boşken ya hiçbir şey ya da
minimal bir satır gösteriyor. İlk açılışta kullanıcı ne yapacağını bilemez.

Öneri: Yönlendirici boş durumlar: simge + kısa açıklama + birincil eylem
butonu (ör. Henüz dönüşüm yok, paket sürükleyerek başla).

### 5. i18n yarım kalmış — ÖNCELİK: ORTA
i18n.ts yalnızca Ayarlar/toplu kartlarını kapsıyor; sayfaların çoğu sabit
Türkçe metin içeriyor. Bu yüzden dil değiştirme (TR/EN) tüm uygulamada
çalışmıyor. (Bu turda lang_tr.py içindeki Çince 原子 artefaktı ve Sidebar
Araclar yazım hatası temizlendi.)

Öneri: Sabit metinleri i18n.ts sözlüğüne taşı; tFor(lang) kullanımını tüm
sayfalara yay ki dil anahtarı gerçekten işe yarasın.

### 6. Güvenlik sayfası sekme yoğun — ÖNCELİK: ORTA
6 sekme (İmza/SBOM/Kalite/Provenance/Sigstore/CVE) çok. Çoğu kullanıcı hepsini
birden ister; bu turda Tüm Kontrolleri Çalıştır eklendi, iyi bir adım.

Öneri: Üstte tek özet kart (tüm kontrollerin tek bakışta durumu), detay için
sekmeler. Sekme başına tek buton yerine sonuçlar otomatik dolsun.

### 7. Tutarlılık — ÖNCELİK: DÜŞÜK
Buton boyutları, boşluklar ve başlık hiyerarşisi sayfalar arası hafif farklılık
gösteriyor. Ortak Card/Button kullanımı iyi ama yer yer boyut/variant seçimleri
tutarsız.

### 8. Erişilebilirlik — ÖNCELİK: DÜŞÜK
Klavye navigasyonu, odak halkaları ve aria-label kullanımı sınırlı. Yol seçici
butonlarına aria-label=path-browse eklendi (bu turda); aynı özen diğer
etkileşimli öğelere de yayılmalı.

---

## Bu turda yapılan UI/UX düzeltmeleri

- Tüm yol alanlarına yerel dosya/klasör seçici (PathPicker): Compare, Export,
  Security. Elle yazma da hâlâ mümkün.
- Security: Tüm Kontrolleri Çalıştır (sıralı, event çakışmasız).
- Dönüştür sekme değiştirince artık durumu kaybetmiyor (her zaman mount).
- Adım göstergesine skipped durumu (malware adımı atlanınca belirsiz kalmaz).
- Snapshot kurulumu gerçekten çalışıyor (pkexec ekranda yetki ister).
- Rollback backend none artık açıklayıcı ve hatasız görünüyor.
- Ayarlar sekmesi takılması giderildi (RPC zaman aşımı + non-blocking dispatch).
- i18n: Çince artefakt ve Araclar yazım hatası temizlendi.

---

## Faz 6 — 8 iyileştirmenin tamamı uygulandı (2026-08)

1. **Navigasyon gruplandı:** Sidebar 5 mantıksal bölüme ayrıldı (Çekirdek,
   Kütüphane, Keşfet, Güvenlik ve Kalite, Sistem). Her bölüm katlanabilir;
   bölüm başlıkları küçük büyük-harf etiketler. Bilişsel yük azaldı.
2. **Dönüşüm ilerleme hissi:** Dönüşüm adımında ilerleme çubuğu belirsiz
   (indeterminate, kayan segment) moda geçer, aktif adım adı ve canlı geçen
   süre sayacı gösterilir. ProgressBar `indeterminate` prop'u kazandı.
3. **Kalıcı sonuç bandı:** Dönüşüm bitince yeşil bir sonuç bandı belirir:
   durum simgesi, tam çıktı yolu ve Kur / Klasörü Aç / Yolu Kopyala / OCI /
   Bağımlılık grafiği butonları. Backend'e `system.open_path` ve
   `system.install_pkg` (pkexec + pacman -U) metotları eklendi.
4. **Boş durumlar:** Compare ve Reports sayfalarına yönlendirici EmptyState
   eklendi (simge + açıklama); Installed'da zaten vardı.
5. **i18n tamamlandı:** Sözlük gezinti, bölüm başlıkları, ortak eylemler ve
   Dönüştür akışını kapsayacak şekilde genişletildi. Sidebar, sayfa başlıkları
   (Topbar), Convert sekmesi ve Installed/Reports ortak butonları `tFor(lang)`
   kullanıyor; dil anahtarı artık uygulamanın ana yüzeylerinde çalışıyor.
6. **Güvenlik özet kartı:** 6 sekmenin üstüne tek bakışta özet kart eklendi;
   her kontrolün durumu (Geçerli/Geçersiz/Temiz/N açık/—) renk kodlu gösterilir
   ve tıklayınca ilgili sekmeye gider.
7. **Tutarlılık:** Ortak Card/Button/Badge kullanımı pekiştirildi; global
   focus-visible halkası ile odak stili tek yerden tutarlı.
8. **Erişilebilirlik:** Global `:focus-visible` halkası (index.css), Sidebar
   bölüm başlıkları ve Güvenlik özet kartlarına focus-visible + aria-label;
   klavye navigasyonu güçlendi.

---

## Öncelik özeti

| # | Konu | Öncelik | Durum |
|---|------|---------|-------|
| 1 | Navigasyon gruplama | Yüksek | ✅ Faz 6 |
| 2 | Dönüşüm ilerleme hissi | Yüksek | ✅ Faz 6 |
| 3 | Kalıcı sonuç bandı | Yüksek | ✅ Faz 6 |
| 4 | Boş durumlar | Orta | ✅ Faz 6 |
| 5 | i18n tamamlama | Orta | ✅ Faz 6 |
| 6 | Güvenlik özet görünüm | Orta | ✅ Faz 6 |
| 7 | Tutarlılık | Düşük | ✅ Faz 6 |
| 8 | Erişilebilirlik | Düşük | ✅ Faz 6 |
