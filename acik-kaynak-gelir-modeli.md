# PkgForge Acik Kaynak Gelir Modeli

> Tek dosya karar belgesi. `MONETIZATION_PLAN.md` + `Acik Kaynak Gelir Modelleri Arastirmasi.md` bu dosyada birlestirilmistir.
> Yasayan belgedir; esik gecisleri `Karar Gunlugu`ne tarihlenerek islenir.
> Son guncelleme: 2026-09-05. Sahip: goun7. Lisans: GPL-3.0-or-later.

## 1. Amac ve ilkeler

PkgForge kisisel ihtiyac + kamu faydasi olarak basladi; hedef simdi ayni kalmak sartiyla surdurulebilir gelir eklemek. En iyi secenek neyse o yapilir; erken paraliastirma yok.

Baglayici ilkeler:

1. Cekirdek (donusturucu + CLI + guvenlik taramasi + SBOM/provenance uretimi) **daima GPL ve ucretsiz** kalir. Cekirdek ozellik paywall arkasina alinmaz.
2. Satilan sey kod degil: **hizmet, sunucu maliyeti olan deger, uyumluluk/destek** olur. Bu GPL ile tam uyumludur.
3. Olcum yoksa parali katman yok. Duygu ile degil esik ile karar verilir (bkz. Bolum 4).
4. Terminolojide **"bagis/yardim/donate" yok**; `Sponsor / Backer / Destekci` kullanilir.
5. Kripto checkout (Hel.io / Helius / Spherepay) kurulmaz. Gerekce: ek entegrasyon + muhasebe yuku + Arch kitlesinde guven erozyonu; getirisi marjinal.

## 2. Mevcut durum (v2.0.0)

- Lisans: **GPL-3.0-or-later**, tek telif sahibi goun7. Bu, gelecek surumleri yeniden lisanslama hakkini sakli tutar; yayinlanmis GPL surumler geri alinamaz.
- Dagitim: AUR paketi henuz yok (PKGBUILD hazir, `v2.0.0` tag + `sha256sums` islenip gonderilecek). AUR adi `pkgforge` **2026-09-05 kontrolunde bostur** (`aur.archlinux.org/packages/pkgforge` 404). Ancak GitHub `pkgforge` organizasyonu doludur (`pkgforge/soar`, 868 star, Rust paket yoneticisi) — marka karismasi riski icin AUR aciklamasinda `Arch Linux .deb/.rpm converter` ibaresi sart, ileride isim eki (`pkgforge-arch`) opsiyonu sakli tutulur.
- UI karari (2026-09-05, kullanici onayi): **Tauri birincil, PyQt6 donduruldu.** Gerekce: 2 GUI = 2 kat test/bakim (38 test dosyasi PyQt'ye bagli, 582 vitest Tauri'de); tek maintainer tasiyamaz. PyQt kodu bu surumde silinmez (suite'yi kizartir); yeni ozellik PyQt'ye eklenmez, sadece guvenlik duzeltmesi yapilir; kaldirma v3.0'da planlanir. Ayrica bkz. `ARCHITECTURE.md`.
- Odeme hesaplari: ikisi de pasif. Kodda hazir (`.github/FUNDING.yml`, `config.DONATE_URL`, README destek bolumu) ama hesaplar acilmamis.

Kullanici gorevleri (Aşama 1 onkosulu):

- [ ] GitHub Sponsors profilini etkinlestir (`github.com/sponsors/goun7`) — adimlar Ek A'da.
- [ ] `polar.sh/goun7` magaza/destek sayfasini aktiflestir — adimlar Ek B'de.
- [ ] 20/B istisna belgesi + ozel banka hesabi icin mali musavir ile gorus (Bolum 7).

## 3. Asama 1 — Sponsorluk (SIMDI, sifir maliyet)

Urun ucretsiz; gonullu destek toplanir. 2026 verisi: GitHub Sponsors bireyselde %0 kesinti (kurumsalda %6'ya kadar), kucuk araclar $50-500/ay, medyan ~$450/ay, bakimcilarin %75+'i sifir aliyor. Yani sponsorluk **kira degil harcik katmani** olarak konumlanir; amaci projeyi yasatmak + Aşama 3'e veri tasimaktir.

| Kanal | Rol | Not |
|---|---|---|
| GitHub Sponsors | Birincil, global | %0 kesinti; README rozeti + her surum notunda link |
| Polar.sh | Ikincil + ileride MoR | Status 2026-09: online; TR satici destekler, KDV yukunu ustlenir |

Tavsiye edilen katmanlar (basit tut, 3 katman):

- Bireysel Destekci: $5-10/ay (isim README'de).
- Profesyonel: $25-50/ay (oncelikli issue yaniti).
- Kurumsal Sponsor: $200+/ay (logo + yol haritasi gorusmesi; kod karari satilmaz).

Yasaklar: karsiliginda ozellik sozu verme, tek sirkete %70+ bagimlilik, sponsor yonetimine haftada 2 saatten fazla.

## 4. Asama 2 — Olcum ve esikler (esik neyi degistiriyor?)

Kullanici sorusu: "esik neyi degistiriyor bilmiyorum." Cevap: esik, **duygu ile parali katmana gecmeyi engelleyen kapi**dir. 2026 basarisizlik oruntusu #1 erken paraliastirmadir: kullanici yokken paywall gelir, topluluk dagilir. Esik sunu soyler:

- Esik ALTINDA: sadece Aşama 1 (sponsorluk) + dagitim + olcum yapilir. Aşama 3 kodu yazilmaz, fiyat aciklanmaz.
- Esik GECILINCE: Aşama 3 **degerlendirilir** (otomatik baslamaz). Degerlendirme = 2 haftalik bakim yuku + odeme egilimi incelemesi + karar gunlugune kayit.

Olcumler (aylik, 10 dakikalik is):

- AUR: oy + popularity + yorum sayisi (`pkgforge` sayfasi).
- GitHub: star, clone, issue acilis hizi.
- Niteliksel: "sirket olarak kullaniyoruz, fatura isteriz" diyenin varligi (en guclu sinyal).

Guncel esikler (bu degerleri ben belirledim; gerekcen asagida):

- **500/ay tekil kurulum VEYA 10 aktif destekci VEYA 2 kurumsal sponsor adayi** → Aşama 3 degerlendirmesi acilir.
- Neden 500/10/2: Arch nişinde 500 kurulum, debtap'in 331 oyu ile kiyaslanabilir ilk cekis demektir; 10 destekci, %0 kesintide bile duzenli geliri ve destegin tekrarlanabilirligini kanitlar; 2 kurumsal aday, open-core icin gerekli B2B sinyalidir. Daha yuksek esik (or. 5000) bu nişte hicbir zaman gecilemez; daha dusuk esik (or. 50) ise 1-2 kisinin hevesini pazar sanir.

## 5. Asama 3 — Open Core (yalnizca veri desteklerse)

Cekirdek GPL kalir. Ucretli olan **yalnizca sunucu/maliyet gerektiren** degerdir; lisans anahtari satmak degil, calisan hizmeti satmak.

Ucretsiz kalan (asla paywall yok): convert, CLI tamami, Tauri masaustu, SBOM/provenance/quality/CVE taramasi uretimi, `doctor`, `audit`, AUR yayin akisi.

Ucretli olabilecek (hepsi hosted, hepsi opsiyonel):

1. Imzali otomatik guncelleme servisi (istemci ucretsiz, imza + barindirma ucretli).
2. Ekip/kurumsal politika profilleri (fleet senkron backend'i hosted).
3. Bulut yedek/senkron backend'i (WebDAV/rclone karsiligi yonetilen alan).

Teknik ilke: kendi sunucu satin alma yok. Dogrulama Polar webhook + Ed25519 imzali kisa omurlu jetonla; agir altyapi (Cloudflare Worker vb.) ilk etapta kurulmaz, Polar'in hosted checkout + musteri portali kullanilir. Fiyat sozu bu asamada verilmez.

## 6. Yapilmayacaklar

- Kripto odeme checkout (Hel.io/Helius/Spherepay) yok.
- Cekirdek ozelligi Pro'ya tasima yok.
- Opt-in olmadan telemetri yok (`health` sayaci varsayilan kapali).
- `main` dalinda fiyat listesi yok (esik oncesi fiyat tartismasi toplulugu kacirir).
- Tek sirkete ozel dal (fork) bakimi yok.

## 7. Vergi ve hukuk (TR baglami, 2026)

Cercekve (guncel kaynaklarla dogrulandi): GVK Mukerrer 20/B istisna siniri 2026'da ~5.300.000 TL, banka %15 stopaj, KDV istisnasi (17/4-a). Sirket kurmadan, defter/fatura yukusuz baslamak icin en pratik yoldur.

Kritik uyarilar (mali musavir/avukat sarti):

1. **Dijital urun satisi tuzagi:** 20/B kapsami "icerik, egitim, veri isleme, mobil uygulama gelistirme"dir; hazir lisans anahtari/binary satisi kapsam disi sayilabilir. Polar uzerinden "Pro lisans sattim, %15 ile kapattim" varsayimi tek basina yetmez — faaliyet niteligi icin ozelge + mali musavir onayi sart.
2. Banka sarti: hasilat yalnizca istisna hesabina yatar; baska hesaba, elden veya kripto ile tahsilat istisnayi bitirir.
3. Sinir asimi: 1 TL bile asim istisnayi bitirir; yillik takip zorunlu.
4. Sozlesme oncesi kisa hukuk gorusu (ozellikle Aşama 3 + dual-license metni icin).

## 8. Dual licensing (pasif firsat)

Biri pkgforge'u kapali urunune gommek isterse ticari lisans pazarligi yapilir. Tek katki sahibi goun7 ve ucuncu taraf Apache-2.0 bilesenler GPLv3 ile uyumlu oldugundan hak saklidir. Talep gelmezse kayip sifirdir; ayri altyapi kurulmaz; proaktif satis yapilmaz.

## 9. Kanal ozeti

| Kanal | Rol | Durum |
|---|---|---|
| GitHub Sponsors | Birincil | Hesap acilacak (Ek A) |
| Polar.sh | MoR + ikincil sponsorluk | Sayfa acilacak (Ek B) |
| iyzico | Yurt ici satis (Aşama 3) | Planli, simdi yok |
| Kripto | Yok | Bilincli ret |

## 10. Karar Gunlugu

| Tarih | Karar | Gerekce |
|---|---|---|
| 2026-09-05 | Tek dosya: bu belge yetkili; eski iki belge hukumsuz | Daginkligi bitir |
| 2026-09-05 | Tauri birincil, PyQt donduruldu (v3.0'da kaldirma) | Bakim yuku; 38 test dosyasi bagimliligi |
| 2026-09-05 | Esikler: 500 kurulum / 10 destekci / 2 kurumsal aday | Nis gercegi + olculebilirlik |
| 2026-09-05 | Kripto checkout yok | Maliyet > fayda |
|  | AUR `pkgforge` gonderimi | Isim bos (404); aciklama farklilastirilacak |
|  | Aşama 3'e gecis degerlendirmesi | Esik gecilince, otomatik degil |

## 11. Kaynaklar ve dogrulama
- AUR bosluk kontrolu: `https://aur.archlinux.org/packages/pkgforge` → 2026-09-05'te 404.
- Polar status: `https://status.polar.sh` → tum servisler online (Eylul 2026).
- 20/B cercevesi: GIB tebligleri + 2026 mali musavir analizleri (~5.3M TL, %15 stopaj, KDV istisnasi).
- Sponsorluk dagilimi: 2026 GitHub Sponsors/Tidelift anketleri (medyan ~$450/ay, %75+ sifir).
- Pazar: StatCounter/Steam 2026 (Linux desktop %3-4), AUR 111.613 paket / 148.159 kullanici (04.09.2026), debtap 1.677 star / 331 oy.

---

## Ek A — GitHub Sponsors acilisi (adim adim, ~30 dk + onay bekleme)

Onkosul: GitHub hesabi + 2FA acik + Turkiye'den basvuru (Stripe Connect TR IBAN odemesi desteklenir).

1. `github.com/sponsors` adresine git → **Join the waitlist / Set up GitHub Sponsors** (hesapta daha once basvuru yoksa) → `Sponsored Developer` profil basvurusunu ac.
2. Basvuru formunu doldur: acik kaynak katki gecmisi otomatik cekilir; bos birakma — pkgforge reposunu "featured work" olarak sec, kisa bio yaz (ornek: "PkgForge — Arch/CachyOS icin guvenli .deb/.rpm donusturucu; tek bakimci, haftada ~X saat").
3. Odeme bilgisi: Stripe Connect uzerinden banka hesabi (20/B istisna hesabinin IBAN'i) + kimlik/vergi bilgisi. Bu adim onaydan once veya sonra istenebilir; bilgiyi hazir tut.
4. Katmanlari tanimla (3 katman yeter; Bolum 3'teki degerler):
   - $5/ay Bireysel Destekci, $25/ay Profesyonel, $200/ay Kurumsal Sponsor; her katmana tek cumle karsilik yaz (ozellik sozu YOK).
5. Basvuruyu gonder. Inceleme genelde gunler surer; red gelirse eksik (profil boslugu, 2FA, bolge belgesi) tamamlanip tekrar basvurulur.
6. Onay sonrasi: bu repodaki `.github/FUNDING.yml` zaten `github: [goun7]` icerdigi icin **Sponsor butonu otomatik belirir** — ek kod gerekmez. README'deki sponsor linki de aktif hale gelir.
7. Her surum notuna tek satir ekle ("Surdurulebilirlik icin sponsor olabilirsiniz") — en yuksek donusum bu noktadadir.
8. Odeme: aylik (ayin 5'i civari), bireysel sponsorlukta %0 kesinti. Gelen tutar 20/B hesabina duser; banka %15 stopaji otomatik keser. Yil sonunda mali musavire tabloyu ver.

## Ek B — Polar.sh acilisi (adim adim, ~30 dk)

Polar MoR'dur: global KDV/satis vergisi yukunu ustlenir; status 2026-09'da online.

1. `polar.sh` → **Get Started** → GitHub hesabinla giris yap.
2. Organizasyon olustur: isim `goun7` (URL `polar.sh/goun7` olur; hesap acilinca `.github/FUNDING.yml` ve `config.DONATE_URL` bu URL'ye cevrilecek — su an Giveth'i isaret ediyor).
3. **Settings → Payouts → Stripe Connect Express** bagla: odeme alici olarak 20/B istisna hesabi IBAN'ini gir. (Polar'in kestigi %5 + $0.50 islem ucreti disinda TR'ye ek aracilik ucreti c magazines; banka tarafi %15 stopaj ayri uygulanir — mali musavirle teyit et.)
4. **Products → Create product** → Aşama 1 icin bagis-nitelikli urun: or. "PkgForge Backer" aylik abonelik ($5 / $25 / $100 uc urun veya tek urunde 3 fiyat katmani). Fayda (benefit) olarak lisans anahtari EKLEME (Aşama 3'e kadar); karsilik olarak isim/logo/tesekkur yaz.
5. Urun checkout linkini ac, test kartiyla 1 $'lik deneme satisi yap → webhook/e-posta akisini dogrula → test urununu arsivle.
6. Magaza sayfasi (`polar.sh/goun7`) herkese acik mi diye kontrol et; acilinca README/FUNDING linklerini buna cevir.
7. Aşama 3'e gecince (esik sonrasi): ayni panele don, ucretli urunlere "License Key" benefit ekle + **Webhooks** menusunden odeme bildirimini kendi dogrulayicina bagla. O gune kadar webhook kodu yazma.

## Ek C — Mali musavir gorusmesi kontrol listesi (tek gorusme, 30 dk)

1. 20/B istisna belgesi basvurusu (ikamet vergi dairesi) + ozel banka hesabi acilisi sirasi.
2. GitHub Sponsors (Stripe Connect → TR IBAN) + Polar (Stripe Connect Express → TR IBAN) gelirlerinin 20/B hasilati sayilip sayilmayacagi; dijital urun satis siniri (Aşama 3 lisans anahtari bu kapsama girer mi?).
3. Sinir takibi: ~5.3M TL esigine yaklasinca ne yapilacak (yillik beyannameye gecis plani).
4. KDV istisnasi (17/4-a) sarti ve sart ihlalinde dogacak yukler.
5. Gorusme notunu tarihle `Karar Gunlugu`ne isle.
