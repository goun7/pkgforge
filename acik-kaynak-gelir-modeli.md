# PkgForge Acik Kaynak Gelir Modeli

> Tek dosya karar belgesi. `MONETIZATION_PLAN.md` + `Acik Kaynak Gelir Modelleri Arastirmasi.md` bu dosyada birlestirilmistir.
> Yasayan belgedir; kararlar `Karar Gunlugu`ne tarihlenerek islenir.
> Son guncelleme: 2026-09-18. Sahip: goun7. Lisans: GPL-3.0-or-later.

## 1. Amac ve ilkeler

PkgForge kisisel ihtiyac + kamu faydasi olarak basladi. Bu belge 2026-09-18'de
**basitlestirilmistir**: uc-asamali plan (sponsorluk -> esik -> open core) bu
niste gerceklesmez; belge 165 satirlik plansiz bir vaat yiginiydi. Yerine
**tek katman**: urun tamamen ucretsiz, pasif sponsorluk acik, gelir beklentisi yok.

Baglayici ilkeler:

1. Cekirdek (donusturucu + CLI + guvenlik taramasi + SBOM/provenance uretimi + Tauri arayuz) **daima GPL ve ucretsiz** kalir. Cekirdek ozellik paywall arkasina alinmaz.
2. Sponsorluk **pasif** bir kanaldir: hesap acik, "Sponsorla" butonu calisir, kimse pazarlanmaz. Gelir bikinlik bir katki olarak gorulur; gelir modeli degil.
3. **Gelir plani, esik veya ucretli katman yoktur.** Bu niste (Arch .deb/.rpm donusturme) pazar kucuktur; en yakin rakip debtap 13 yilda 331 oy biriktirdi. Onceki 500/ay kurulum esigi erisilemezdi ve dolayisiyla Aşama 3'e giden yol bos bir vaatti — bu, projenin "fake/stub yok" kuralina aykiri.
4. Terminolojide **"bagis/yardim/donate" yok**; `Sponsor / Backer / Destekci` kullanilir.
5. Kripto checkout kurulmaz. Gerekce: ek entegrasyon + muhasebe yuku + Arch kitlesinde guven erozyonu; getirisi marjinal.
6. Opt-in olmadan telemetri yok; `main` dalinda fiyat listesi yok; cekirdek ozelligi Pro'ya tasima yok.

## 2. Mevcut durum (v2.2.0)

- Lisans: **GPL-3.0-or-later**, tek telif sahibi goun7. Bu, gelecek surumleri yeniden lisanslama hakkini sakli tutar; yayinlanmis GPL surumler geri alinamaz.
- Dagitim: AUR `pkgforge` 2.2.0-4 (2026-09-18'de gonderildi; Tauri desktop + Python sidecar dahil). 0 oy, 0 popularity — yeni. GitHub: 2 star, 4 acik issue. Odak **benimseyis**, gelir degil.
- UI karari (2026-09-05, kullanici onayi): **Tauri birincil, PyQt6 donduruldu.** Gerekce: 2 GUI = 2 kat test/bakim (38 test dosyasi PyQt'ye bagli, 582 vitest Tauri'de); tek maintainer tasiyamaz. PyQt kodu bu surumde silinmez (suite'yi kizartir); yeni ozellik PyQt'ye eklenmez, sadece guvenlik duzeltmesi yapilir; kaldirma v3.0'da planlanir. Ayrica bkz. `ARCHITECTURE.md`.
- **Sponsorluk kanallari acilmamis.** 2026-09-18 itibariyla Giveth `Raised: 0`, GitHub Sponsors profili ve Polar magazasi pasif. Bu belgenin TEK eylem maddesi budur (Ek A).

## 3. Sponsorluk (tek katman, pasif)

Urun ucretsiz; gonullu destek toplanir. 2026 verisi: GitHub Sponsors bireyselde %0 kesinti (kurumsalda %6'ya kadar), kucuk araclar medyan ~$450/ay, bakimcilarin %75+'i sifir aliyor. Yani sponsorluk **kira degil harcik katmani** olarak konumlanir; amaci projeyi yasatmaktir. Gelir beklentisi: sifir bazinda.

| Kanal | Rol | Not |
|---|---|---|
| GitHub Sponsors | Birincil, global | %0 kesinti; Turkiye destekli bolgelerde (dogrulandi, bkz. Kaynaklar). README rozeti + her surum notunda link |
| Polar.sh | Ikincil | Status 2026-09: online; acilinca `polar.sh/goun7` |

Katmanlar (basit tut, 3 katman; karsiliginda **ozellik sozu yok**):

- Bireysel Destekci: $5-10/ay (isim README'de).
- Profesyonel: $25-50/ay (oncelikli issue yaniti).
- Kurumsal Sponsor: $200+/ay (logo + yol haritasi gorusmesi; kod karari satilmaz).

Yasaklar: karsiliginda ozellik sozu verme, tek sirkete %70+ bagimlilik, sponsor yonetimine haftada 2 saatten fazla.

## 4. Neden eski plan cikarildi (kanit)

Onceki belge uc asamaydi: (1) sponsorluk, (2) 500/ay kurulum veya 10 destekci veya 2 kurumsal aday esigi, (3) ucretli hosted open core. 2026-09-18 derin denetimde bu kaldirildi:

1. **Esik erisilemezdi.** Esik gerekcesi "debtap'in 331 oyu ile kiyaslanabilir ilk cekis"di; ama debtap o 331 oya **13 yilda** ulasti. Aylik 500 tekil kurulum, nişin en buyuk oyuncusunun 13 yillik toplamini her asmak demek. Esikin tutarli tek sonucu: Aşama 3 asla acilmaz, yani vaat bos kalirdi.
2. **Hosted model mimaride kapali.** PEXT (2025, OSS dev tools ekonomisi): "hosted service models achieve monetization 40% faster on average than pure open core" — ama PkgForge'un sync backend'leri kullanici kendi URL'ini getirir (WebDAV/rclone/git), sidecar tamamen yerel stdio JSON-RPC, delta guncellemeler kullanici URL'ine gider. Sunucu satin almayi reddediyoruz; en hizli gelir modeli mimari karariyla kapali.
3. **Para kalite getirmez.** Alami, Pardo & Linaker (2024, arXiv:2402.06916, 217 ASF projesi): "selected sustainability metrics do not significantly affect defect density or code coverage." Projenin asil hedefi "sıfır hata, %100 kullanici deneyimi" — sponsorluk bunu saglamaz; bakimci zamani ve odak saglar.
4. **Kurumsal/pazar gerekliligi yok.** 2 star / 0 oy / 4 acik issue ile Aşama 3 B2B sinyali (2 kurumsal aday) olusmamistir.

Sonuc: uc-asamali plan sadelestirildi. Belge 165 satirdan ~45 satira indi; eylemsiz vaatler cikarildi.

## 5. Yapilmayacaklar

- Kripto odeme checkout (Hel.io/Helius/Spherepay) yok.
- Cekirdek ozelligi Pro'ya tasima yok; lisans anahtari satisi yok.
- Opt-in olmadan telemetri yok (`health` sayaci varsayilan kapali).
- `main` dalinda fiyat listesi yok.
- Tek sirkete ozel dal (fork) bakimi yok.
- **Sifir gelir varken mali musavir/avukat gorusmesi yok.** GVK 20/B istisnasi yalnizca hasilat olusunca gecerlidir; o gune kadar banka stopaj/istisna takibi yuku yoktur. (Onceki Ek C kaldirildi.)
- **Webhook/odeme dogrulama altyapisi yazilmayacak.** Polar webhook + Ed25519 jeton yalnizca gercek bir ucretli urun kararlastirilirsa gerekecek; o gun gelene kadar kod yazmak mock/stub uretir.

## 6. Dual licensing (pasif firsat)

Biri pkgforge'u kapali urunune gommek isterse ticari lisans pazarligi yapilir. Tek katki sahibi goun7 ve ucuncu taraf Apache-2.0 bilesenler GPLv3 ile uyumlu oldugundan hak saklidir. Talep gelmezse kayip sifirdir; ayri altyapi kurulmaz; proaktif satis yapilmaz.

## 7. Kanal ozeti

| Kanal | Rol | Durum |
|---|---|---|
| GitHub Sponsors | Birincil | Hesap acilacak (Ek A) |
| Polar.sh | Ikincil | Sayfa acilacak (Ek B) |
| Kripto | Yok | Bilincli ret |
| Ucretli katman / hosted | **Kaldirildi** | Esik erisilemez, mimariye ters |

## 8. Karar Gunlugu

| Tarih | Karar | Gerekce |
|---|---|---|
| 2026-09-18 | **3-asamali plan kaldirildi; tek katman pasif sponsorluk** | Esik erisilemez (debtap 331 oy/13 yil); hosted mimariye ters (PEXT 2025); para kalite getirmez (Alami 2024) |
| 2026-09-18 | Mali musavir gorusmesi donduruldu (Ek C kaldirildi) | Sifir gelirde vergi yuku yok |
| 2026-09-05 | Tek dosya: bu belge yetkili; eski iki belge hukumsuz | Daginkligi bitir |
| 2026-09-05 | Tauri birincil, PyQt donduruldu (v3.0'da kaldirma) | Bakim yuku; 38 test dosyasi bagimliligi |
| 2026-09-05 | Kripto checkout yok | Maliyet > fayda |
| 2026-09-05 | AUR `pkgforge` gonderimi (2.2.0-4 ile tamamlandi) | Isim bos (404); aciklama farklilastirildi |

## 9. Kaynaklar ve dogrulama

- GitHub Sponsors destekli bolgeler: `https://docs.github.com/en/sponsors/getting-started-with-github-sponsors/about-github-sponsors` → Turkiye listede (2026-09-18).
- PEXT (2025), "The Economics of Open Source Dev Tools": hosted modeller open core'dan %40 daha hizla gelir uretir; stars↔funding iliskisi zayif; community-only projeler ~$200k sponsorluk (buyuk projelerde, medyan degil).
- Alami, Pardo, Linåker (2024), arXiv:2402.06916, DOI 10.48550/arXiv.2402.06916: sustainability metrikleri defect density/code coverage'i anlamli etkilemez.
- Sponsorluk dagilimi: 2026 GitHub Sponsors/Tidelift anketleri (medyan ~$450/ay, %75+ sifir).
- Pazar: AUR `pkgforge` 0 oy / 0 pop (2026-09-18); debtap 331 oy / 13 yil dormant; yay 2654 oy, paru 1256 oy.
- Giveth `giveth.io/project/pkgforge`: `Raised":0,"totalDistributed":0` (2026-09-18).

---

## Ek A — GitHub Sponsors acilisi (adim adim, ~30 dk + onay bekleme)

Onkosul: GitHub hesabi + 2FA acik + Turkiye'den basvuru (Stripe Connect TR IBAN odemesi desteklenir; Turkiye destekli bolgelerde — dogrulandi).

1. `github.com/sponsors` adresine git → **Join the waitlist / Set up GitHub Sponsors** → `Sponsored Developer` profil basvurusunu ac.
2. Basvuru formunu doldur: acik kaynak katki gecmisi otomatik cekilir; pkgforge reposunu "featured work" olarak sec, kisa bio yaz.
3. Odeme bilgisi: Stripe Connect uzerinden banka hesabi IBAN'i + kimlik/vergi bilgisi.
4. Katmanlari tanimla (3 katman; Bolum 3'teki degerler): $5/ay Bireysel Destekci, $25/ay Profesyonel, $200/ay Kurumsal Sponsor; her katmana tek cumle karsilik yaz (ozellik sozu YOK).
5. Basvuruyu gonder. Inceleme genelde gunler surer; red gelirse eksik tamamlanip tekrar basvurulur.
6. Onay sonrasi `.github/FUNDING.yml`'ye `github: [goun7]` ekle (su an bilincli olarak bos — yaniltici Sponsor butonu olmasin). README'deki sponsor linki de aktif hale gelir.
7. Her surum notuna tek satir ekle ("Surdurulebilirlik icin sponsor olabilirsiniz").
8. Odeme: aylik (ayin 5'i civari), bireysel sponsorlukta %0 kesinti. Gelen tutar banka hesabina duser; banka %15 stopaji otomatik keser. Yil sonunda mali musavire tabloyu ver (gelir olusursa).

## Ek B — Polar.sh acilisi (adim adim, ~30 dk)

Polar MoR'dir: global KDV/satis vergisi yukunu ustlenir; status 2026-09'da online.

1. `polar.sh` → **Get Started** → GitHub hesabinla giris yap.
2. Organizasyon olustur: isim `goun7` (URL `polar.sh/goun7` olur; hesap acilinca `.github/FUNDING.yml` ve `config.DONATE_URL` bu URL'ye cevrilecek — su an Giveth'i isaret ediyor).
3. **Settings → Payouts → Stripe Connect Express** bagla: odeme alici olarak banka hesabi IBAN'ini gir.
4. **Products → Create product** → bagis-nitelikli urun: "PkgForge Backer" aylik abonelik ($5 / $25 / $100). Fayda (benefit) olarak lisans anahtari EKLEME; karsilik olarak isim/logo/tesekkur yaz.
5. Urun checkout linkini ac, test kartiyla 1 $'lik deneme satisi yap → webhook/e-posta akisini dogrula → test urununu arsivle.
6. Magaza sayfasi herkese acik mi diye kontrol et; acilinca README/FUNDING linklerini buna cevir.
7. **Webhook/odeme dogrulama kodu YAZMA** — yalnizca gercek bir ucretli urun kararlasilirsa gerekir (bkz. Bolum 5).
