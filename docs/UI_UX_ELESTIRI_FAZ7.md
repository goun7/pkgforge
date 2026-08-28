# PkgForge Desktop — Kapsamlı UI/UX Eleştirisi ve Öneriler (Faz 7)

Faz 6'da 8 ana iyileştirme tamamlandı. Bu belge, mevcut Tauri + React
arayüzünün **geriye kalan tüm eleştiri ve geliştirme önerilerini** kod referanslarıyla
birlikte toplar. Model görüntü göremediği için her madde doğrudan kaynak koda
dayanır. 2026-08 değerlendirmesi.

Öncelik etiketleri: **[Y] Yüksek · [O] Orta · [D] Düşük**

---

## 1. Bilgi Mimarisi ve Navigasyon

### 1.1 Topbar atıl duruyor [Y]
`App.tsx`, `Topbar`'a ne `onSearchClick` ne de `right` prop'u geçirir. Yani
Topbar yalnızca sayfa başlığını gösterir; sağ taraf tamamen boş. `Topbar.tsx`
zaten bir "Ara… ⌘K" butonu ve `right` slotu destekliyor ama hiç kullanılmıyor.

**Öneri:**
- Sağ tarafa kalıcı **dil değiştirici (TR/EN)** ve **tema değiştirici** koy —
  şu an dil/tema yalnızca Ayarlar'ın derininde. Bu, en sık istenen iki ayarı
  tek tık yapar.
- Sidecar bağlantı durumu (çevrimiçi/çevrimdışı) için küçük bir gösterge ekle.
- Ya ⌘K komut paletini gerçekten implement et, ya da ölü vaadi kaldır.

### 1.2 Komut paleti (⌘K) yok [O]
⌘K ipucu gösteriliyor ama işlev yok. 12 sayfalı bir uygulamada komut paleti
(hızlı sayfa geçişi + eylem arama) gezinmeyi çok hızlandırır.

### 1.3 Klavye kısayolları yok [O]
Sayfalar arası geçiş için `1..9` veya `Ctrl+Tab`, dönüştürmeyi başlatmak için
`Ctrl+Enter` gibi kısayollar yok. Sadece DropZone Enter/Space destekliyor.

**Öneri:** Global bir `useHotkeys` katmanı: rakamlarla sayfa geçişi, `Ctrl+Enter`
ile dönüştürmeyi başlat, `Esc` ile çalışan dialog'u kapat (Dialog'da var ama global değil).

### 1.4 Sidebar dar pencerede küçülemiyor [D]
Sidebar sabit `w-56`. Dar pencerelerde içeriği sıkıştırır. Sadece simge moduna
geçen bir "collapse" (veya belirli genişliğin altında otomatik daralma) yok.

---

## 2. Görsel Tasarım ve Hiyerarşi

### 2.1 Başlık hiyerarşisi zayıf [Y]
`Topbar` h1 = `text-base` (16px), `CardTitle` = `text-base` (16px). Sayfa başlığı
ile kart başlığı aynı boyutta; görsel hiyerarşi yok. Kullanıcı "neredeyim"i
başlık boyutundan anlayamıyor.

**Öneri:** Topbar h1'i `text-lg/xl` yap; CardTitle `text-base` kalsın. Böylece
Sayfa > Kart > İçerok hiyerarşisi netleşir.

### 2.2 `--text-muted` kontrastı düşük [O]
`--text-muted: #5a6478` koyu zemin (#0a0e1a) üzerinde küçük metinlerde düşük
kontrast. Birçok yer (log boş durumu, kuyruk boş, ipuçları) önemli bilgiyi
`text-muted` ile gösteriyor. WCAG AA için küçük metinde 4.5:1 gerekir.

**Öneri:** `--text-muted`'ı biraz aydınlat (#6b7688 civarı) veya bilgi taşıyan
metinlerde `text-secondary` kullan; muted'ı yalnızca dekoratif öğelere sakla.

### 2.3 Açık tema uygulanıyor ama geçiş sert [D]
`Settings.tsx:142` `data-theme` attribute'unu ayarlıyor; `tokens.css` light
değerleri tanımlıyor. İyi. Ama tema değişimi ani (geçiş animasyonu yok) ve
yalnızca ayarlar kaydedilince tetikleniyor — önizleme yok.

**Öneri:** Tema seçiminde anında önizleme + `transition-standard` ile yumuşak geçiş.

### 2.4 Marka vurgusu az [D]
Gradient (mavi->ember) sadece logo ve progress bar'da. Uygulama genel olarak
düz ve "template" hissi veriyor. Birincil eylemlerde (Başlat, Kur) gradient
veya belirgin bir vurgu rengi markayı güçlendirir.

---

## 3. Etkileşim ve Geri Bildirim

### 3.1 Toast'lar çok kısa ve kapatılamıyor [Y]
`Toast.tsx` her toast'ı 4 saniyede siler; elle kapatma (X) yok, eylem butonu yok.
Hata toast'ları (özellikle uzun makepkg/pacman hataları) okunamadan kaybolur.
Ayrıca üst üste çok toast birikebilir (sınır yok).

**Öneri:**
- Kapatma (X) butonu ekle.
- Hata toast'ları daha uzun kalsın (örn. 8sn) veya kullanıcı kapatana kadar dursun.
- Maksimum görünür toast sayısı (örn. 4) + en eskiyi düşürme.
- Kritik sonuçlar için toast yerine kalıcı band (Faz 6'da dönüşüm için yapıldı;
  kurulum/export sonuçlarına da yay).

### 3.2 Yıkıcı eylemlerde onay/geri alma yok [Y]
`Installed`'da "Temizle" (tüm geçmişi siler) ve tek tek "Kaldır" doğrudan çalışır;
onay dialog'u veya "geri al" yok. `history.clear` geri dönüşsüz.

**Öneri:** Yıkıcı eylemlerde `Dialog` ile onay iste; mümkünse "X saniye içinde geri al"
snackback'i göster.

### 3.3 Adım göstergesi ham İngilizce anahtar gösteriyor [Y]
`Convert.tsx:473` `<StepIndicator statuses={statuses} />` çağrısı `labels` prop'u
geçirmiyor. `StepIndicator` bu yüzden alt etiket olarak ham anahtarları
("security", "malware", "analysis"…) CSS `capitalize` ile gösteriyor. Dil TR de
olsa EN de olsa adım adları İngilizce ve teknik kalıyor.

**Öneri:** `STEP_LABEL_KEYS` (Faz 6'da eklendi) üzerinden yerelleştirilmiş etiketleri
`labels` olarak geçir: `<StepIndicator statuses={statuses} labels={stepLabels} />`.

### 3.4 LogViewer kontrolsüz [O]
`LogViewer` her satırda `scrollIntoView({behavior:"smooth"})` çağırır. Uzun
dönüşümde (binlerce satır) bu hem performanslı değil hem de kullanıcı yukarı
kaydırıp okumak istese bile sürekli aşağı snap'lenir. Kopyalama/temizleme yok.

**Öneri:**
- Kullanıcı yukarı kaydırdıysa otomatik kaydırmayı durdur (en alta inince tekrar aç).
- Sanal listeleme veya satır sınırı (son N satır).
- "Log'u kopyala" ve "Temizle" butonları.
- smooth yerine otomatik (instant) scroll — her satırda smooth animasyon gereksiz.

### 3.5 Async butonlarda yük durumu tutarsız [O]
Bazı butonlar spinner gösteriyor (Ara, Derle, Doğrula), bazıları göstermiyor
(Installed Kaldır/Geri al, Updates Etkinleştir, Fleet Push). Tıklayınca ne olduğu
belirsiz kalabiliyor.

**Öneri:** Tüm async butonlarda tutarlı spinner + disabled durumu. Bir
`<AsyncButton>` soyutlaması bunu merkezileştirir.

### 3.6 DropZone kabul ettiği türleri görsel anlatmıyor [D]
DropZone metin olarak türleri listeliyor ama görsel ipucu (simge rozetleri,
örnek dosya kartları) yok. İlk kez kullanan biri ne bırakabileceğinden emin olamaz.

---

## 4. İçerik, Mikro-metin ve i18n

### 4.1 i18n hâlâ kısmi [Y]
Faz 6'da gezinti, başlıklar, Convert ve bazı ortak butonlar çevrildi ama
**Browse, Updates, Export, Security, Fleet, Plugins, Tools, Settings alan etiketleri**
hâlâ sabit Türkçe. Dil EN yapılınca bu sayfalar Türkçe kalmaya devam ediyor.

**Öneri:** Kalan tüm sayfaları sözlüğe taşı. Bu, "dil anahtarı tüm uygulamada
çalışsın" hedefinin gerçekten tamamlanması için şart.

### 4.2 Fleet sayfası Türkçe karakter kullanmıyor [O]
`Fleet.tsx` metinleri diyakritiksiz: "gecmis kayit", "yapilandirildi",
"Senkron tamamlandi", "basarisiz", "Durum Ozeti". Uygulamanın geri kalanı düzgün
Türkçe kullanırken bu sayfa özensiz görünüyor (muhtemelen eski kod).

**Öneri:** Fleet metinlerini düzgün Türkçeye çevir ve i18n sözlüğüne taşı.

### 4.3 StatusPill ham İngilizce durum gösteriyor [O]
`StatusPill`, `Badge` içinde ham durumu basar: "success", "failed", "pending",
"running", "cancelled". Installed tablosunda ve QueueList'te kullanıcıya İngilizce
teknik terim gösterilir.

**Öneri:** Durumları yerelleştir ("Başarılı", "Beklemede", "Çalışıyor"…) veya en
azından bir etiket haritası kullan.

### 4.4 Terminoloji tutarsızlığı [D]
"Dönüştür / Dönüşüm / Dönüştürme", "Kur / Kurulum / Kurulu" gibi yakın ama farklı
kullanımlar var. Tek bir terim sözlüğü (glossary) belirlenip her yerde aynı
kullanılmalı.

---

## 5. Erişilebilirlik

### 5.1 Dialog'da odak tuzağı yok [Y]
`Dialog.tsx` Escape ve backdrop tıklamasını destekliyor, `aria-modal` var; ama
**odak tuzağı (focus trap) yok**: dialog açılınca odak içeri taşınmıyor, Tab ile
arkadaki içeriğe kaçılıyor, kapanınca odak geri verilmiyor.

**Öneri:** Açılışta odağı dialog'a taşı, Tab'ı dialog içinde döndür, kapanışta
odağı tetikleyen öğeye iade et.

### 5.2 aria-label'lar İngilizce ve genel [O]
Icon-only butonların `aria-label`'ları İngilizce ve şablon: "close", "drop-zone",
"path-browse", "uninstall X", "info X". Ekran okuyucu kullanıcıları için bunlar
yerelleştirilmiş ve açıklayıcı olmalı.

### 5.3 Tablolarda semantik eksik [D]
`Installed` ve Updates cross-check tablolarında `<th scope="col">` yok, tablo
`<caption>` taşımıyor. Ekran okuyucular için tablo yapısı zayıf.

### 5.4 Renk + metin genelde iyi [—]
Badge'ler renk + metin, StepIndicator renk + ikon kullanıyor (iyi). Sadece-renk
durum gösterimi büyük ölçüde yok. Bu korunmalı.

---

## 6. Performans Algısı

### 6.1 LogViewer sanal değil [O]
Her yeni satırda tüm liste yeniden render edilir. Uzun dönüşümde binlerce satır
DOM'a eklenir; bu arayüzü yavaşlatabilir. (Bkz. 3.4.)

### 6.2 Flatpak listesi her girişte yeniden yükleniyor [D]
`Export.tsx` her mount'ta `export.flatpak_list` çağırır. Sayfalar arası geçişte
(Export unmount olup yeniden mount olur) gereksiz tekrar çağrı.

**Öneri:** Sonucu kısa süreli cache'le veya App seviyesinde tut.

### 6.3 Installed 200 kaydı sayfalama olmadan yüklüyor [D]
`history.list {limit:200}` tek seferde çekilir; sıralama/sayfalama yok. Çok kayıtta
tablo ağır ve taraması zor.

---

## 7. Tutarlılık

### 7.1 Buton/input boyutları değişken [O]
Toolbar'da kimi buton `size="sm"` kimi varsayılan `md`; input yükseklikleri
`h-9` ile `h-10` arasında değişiyor. Aynı bağlamda (kart başlığı eylemleri)
bile farklı boyutlar var.

**Öneri:** Kart başlığı eylemleri için standart `size="sm"`; form inputları için
standart yükseklik. Tasarım token'larında "eylem boyutu" kuralı tanımla.

### 7.2 Boş/yüklenme durumları tutarsız [O]
Bazı sayfalar `Skeleton` (Browse, Updates, Export), bazıları düz metin
("Sonuç bulunamadı", "Flatpak uygulaması bulunamadı"), bazıları `EmptyState`
(Installed, Reports, Compare) kullanıyor. Aynı durum üç farklı şekilde sunuluyor.

**Öneri:** Tek bir karar ağacı: yüklenirken Skeleton, boşsa EmptyState, hata ise
hata durumu. Tüm sayfalara uygula.

### 7.3 Kart başlığı düzeni değişken [D]
Kimi CardHeader `flex-row justify-between` (sağda eylem), kimi değil; kimi
CardTitle ikonlu, kimi ikonsuz. Hafif görsel tutarsızlık.

---

## 8. Hata Yönetimi ve Kenar Durumları

### 8.1 Global hata sınırı yok [O]
Bir bileşen render'da hata verirse tüm uygulama beyaz ekrana düşer. React
`ErrorBoundary` yok.

**Öneri:** App etrafında ErrorBoundary + "Bir şeyler ters gitti, yeniden dene" ekranı.

### 8.2 Sidecar hazır değilken ilk yükleme hataları [O]
Sayfalar mount'ta RPC çağırır; sidecar yavaşsa ilk açılışta error toast'ları
patlayabilir. "Bağlanıyor…" durumu yok.

**Öneri:** Sidecar hazır olana kadar hafif bir "bağlanıyor" durumu; hazır değilken
çağrıları kuyruğa al veya yumuşak yeniden dene.

### 8.3 Hatalarda yeniden deneme yok [D]
Çoğu catch sadece toast basar. Ağır işlerde (export, build) "Yeniden dene" butonu yok.

---

## 9. İlk Açılış / Onboarding

### 9.1 Karşılama/rehber yok [O]
İlk açılışta kullanıcı boş bir DropZone ile karşılanır. Uygulamanın ne yaptığı,
nasıl başlanacağı anlatılmaz. Özellik zenginliği (12 sayfa) keşfedilmeyi bekler.

**Öneri:** İlk çalıştırmada kısa bir karşılama (3 adım: paket bırak -> dönüştür ->
kur) veya DropZone içine "Nasıl çalışır" ipucu. İsteğe bağlı "tur" (coach marks).

### 9.2 Gelişmiş özellikler açıklanmıyor [D]
Provenance, Sigstore, Fleet, delta-update gibi kavramlar için bağlam içi yardım
(tooltip / "bu nedir?") yok. Yeni kullanıcı bunların değerini anlayamaz.

---

## 10. Sayfa Bazlı Spesifik Eleştiriler

- **Security:** 6 sekme hâlâ yoğun. "Tüm Kontrolleri Çalıştır" sonuçları dolduruyor
  ama her sekmede ayrı manuel buton (Doğrula/Tara) duruyor — gereksiz tekrar.
  Sonuçlar otomatik doluyorsa manuel butonlar ikincil olmalı veya kalkmalı. [O]
- **Convert:** Kuyruk kartı boşken bile görünür ("Kuyruk boş"). Boşken daha az yer
  kaplayabilir veya DropZone ile birleşebilir. Kaynaktan sihirbazı sadece URL alır;
  doğrulama/önizleme yok. [D]
- **Updates:** Birbirinden bağımsız 3 kart (Delta, Zamanlanmış, Cross-check) tek
  sayfada; Delta deneysel ve varsayılan kapalı ama en üstte sunuluyor. Kaygılar
  ayrılmalı veya Delta alta alınmalı. [D]
- **Browse:** Sonuçlar 25 ile sınırlı, "daha fazla yükle" yok. Oy sayısı/durum iyi
  ama açıklama kırpılıyor (truncate) — tam açıklama için tooltip yok. [D]
- **Fleet:** Diyakritiksiz Türkçe (bkz. 4.2) + backend listesi sadece metin; durum
  rozetleri ("HAZIR"/"YOK") büyük harf ve tutarsız. [O]
- **Settings:** Çok uzun tek sayfa (562 satır, ~10 kart). Alt bölümlere (Genel /
  Güvenlik / Bulut / Gelişmiş) sekmelenirse taranması kolaylaşır. Ayar arama yok. [O]

---

## 11. Öncelik Özeti

| # | Konu | Öncelik | Kategori |
|---|------|---------|----------|
| 1.1 | Topbar'a dil/tema/durum + boş alanı kullan | Y | Navigasyon |
| 3.1 | Toast: kapatma, süre, eylem, sınır | Y | Geri bildirim |
| 3.2 | Yıkıcı eylemlerde onay/geri al | Y | Etkileşim |
| 3.3 | StepIndicator yerelleştirilmiş etiket | Y | i18n |
| 4.1 | Kalan sayfaların i18n'i | Y | i18n |
| 5.1 | Dialog odak tuzağı | Y | Erişilebilirlik |
| 2.1 | Başlık hiyerarşisi | Y | Görsel |
| 2.2 | text-muted kontrastı | O | Görsel |
| 3.4 | LogViewer kontrol + performans | O | Etkileşim |
| 3.5 | Async buton spinner tutarlılığı | O | Etkileşim |
| 4.2 | Fleet diyakritik düzeltmesi | O | İçerik |
| 4.3 | StatusPill yerelleştirme | O | i18n |
| 5.2 | aria-label yerelleştirme | O | Erişilebilirlik |
| 7.1 | Buton/input boyut tutarlılığı | O | Tutarlılık |
| 7.2 | Boş/yüklenme durum standardı | O | Tutarlılık |
| 8.1 | ErrorBoundary | O | Hata |
| 8.2 | Sidecar "bağlanıyor" durumu | O | Hata |
| 9.1 | Onboarding / karşılama | O | Onboarding |
| 10 | Settings sekmelenme | O | Sayfa |
| 1.2 | ⌘K komut paleti | O | Navigasyon |
| 1.3 | Klavye kısayolları | O | Navigasyon |
| 2.3 | Tema önizleme + geçiş | D | Görsel |
| 2.4 | Marka vurgusu | D | Görsel |
| 1.4 | Sidebar daraltma | D | Navigasyon |
| 3.6 | DropZone görsel ipucu | D | Etkileşim |
| 4.4 | Terim sözlüğü | D | İçerik |
| 5.3 | Tablo semantiği | D | Erişilebilirlik |
| 6.2/6.3 | Cache + sayfalama | D | Performans |
| 8.3 | Yeniden deneme butonları | D | Hata |
| 9.2 | Bağlam içi yardım | D | Onboarding |

---

## 12. Önerilen Uygulama Sırası (sonraki fazlar)

**Faz 7A (Yüksek, hızlı kazanımlar):**
1. Topbar'a dil/tema değiştirici + sidecar durum göstergesi (1.1)
2. Toast iyileştirmeleri: X ile kapatma, hata için uzun süre, sınır (3.1)
3. StepIndicator'a yerelleştirilmiş etiket geçir (3.3)
4. Dialog odak tuzağı (5.1)
5. Başlık hiyerarşisi: Topbar h1 büyüt (2.1)

**Faz 7B (i18n tamamlama):**
6. Kalan tüm sayfaları i18n sözlüğüne taşı (4.1)
7. StatusPill + Fleet diyakritik + aria-label yerelleştirme (4.2, 4.3, 5.2)

**Faz 7C (Etkileşim + tutarlılık):**
8. Yıkıcı eylem onayları (3.2)
9. LogViewer kontrolü + AsyncButton soyutlaması (3.4, 3.5)
10. Boş/yüklenme durum standardı + buton boyut tutarlılığı (7.1, 7.2)

**Faz 7D (Sağlamlık + onboarding):**
11. ErrorBoundary + sidecar "bağlanıyor" durumu (8.1, 8.2)
12. Onboarding karşılama + Settings sekmelenme (9.1, 10)


---

## Faz 7 — Uygulama Durumu (2026-08)

30 onerinin **tamami uygulandi**. Dogrulama: frontend 95/95 test, Python
kapsama %100, production build basarili.

| # | Konu | Durum | Uygulama |
|---|------|-------|----------|
| 1.1 | Topbar dil/tema/durum | ✅ | TopbarActions.tsx |
| 1.2 | Komut paleti (Ctrl+K) | ✅ | CommandPalette.tsx |
| 1.3 | Klavye kisayollari (Alt+1..9) | ✅ | App.tsx |
| 1.4 | Sidebar daraltma | ✅ | Sidebar.tsx (compact mod) |
| 2.1 | Baslik hiyerarsisi | ✅ | Topbar h1 text-lg |
| 2.2 | text-muted kontrast | ✅ | tokens.css |
| 2.3 | Tema gecisi + onizleme | ✅ | lib/theme.ts + theme-switching CSS |
| 2.4 | Marka vurgusu | ✅ | Button primary gradient |
| 3.1 | Toast (X, sure, sinir, eylem) | ✅ | Toast.tsx yeniden |
| 3.2 | Yikici eylem onayi | ✅ | ConfirmDialog.tsx + Installed |
| 3.3 | StepIndicator etiket | ✅ | Convert.tsx labels |
| 3.4 | LogViewer kontrol | ✅ | LogViewer.tsx (stick/copy/clear/limit) |
| 3.5 | AsyncButton | ✅ | AsyncButton.tsx + Fleet |
| 3.6 | DropZone gorsel ipucu | ✅ | DropZone.tsx tur rozetleri |
| 4.1 | Kalan sayfalarin i18n'i | ✅ | 8 sayfa sozluge tasindi |
| 4.2 | Fleet diyakritik | ✅ | Fleet.tsx + Tools.tsx |
| 4.3 | StatusPill yerellesme | ✅ | StatusPill.tsx |
| 4.4 | Terim sozlugu | ✅ | docs/TERIM_SOZLUGU.md |
| 5.1 | Dialog odak tupu | ✅ | Dialog.tsx focus trap |
| 5.2 | aria-label yerellesme | ✅ | DropZone/Installed/Browse/Plugins/Tools |
| 5.3 | Tablo semantegi | ✅ | scope/caption eklendi |
| 6.2 | Flatpak cache | ✅ | Export.tsx modul cache |
| 6.3 | Installed sayfalama | ✅ | Installed.tsx load-more |
| 7.1 | Buton/input boyut | ✅ | Input h-9 standardi |
| 7.2 | Bos durum standardi | ✅ | EmptyState/Skeleton tutarliligi |
| 8.1 | ErrorBoundary | ✅ | ErrorBoundary.tsx + main.tsx |
| 8.2 | Sidecar baglaniyor | ✅ | TopbarActions (Loader2/Wifi/WifiOff) |
| 8.3 | Yeniden deneme | ✅ | Export sonuc rozetine retry |
| 9.1 | Onboarding | ✅ | Onboarding.tsx (ilk calistirma) |
| 9.2 | Baglam ici yardim | ✅ | InfoTip.tsx (Delta/Security/Fleet/Schedule) |
| 10 | Settings sekmelenme | ✅ | Settings.tsx (Genel/Profiller/Bulut) |

### Eklenen yeni bilesenler
- components/TopbarActions.tsx, CommandPalette.tsx, Onboarding.tsx, ErrorBoundary.tsx
- components/ui/AsyncButton.tsx, ConfirmDialog.tsx, InfoTip.tsx
- lib/theme.ts
- docs/TERIM_SOZLUGU.md

### Notlar
- i18n sozlugu ~150 yeni anahtar (tr+en) iceriyor; 8 sayfa tam baglandi.
- Dialog odak tupu, Toast eylem/sinir, tema gecisi gibi etkilesim iyilestirmeleri
  mevcut testlere uyarlanarak dogrulandi.

