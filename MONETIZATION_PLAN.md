# PkgForge Gelir Modeli Plani

Bu belge, "Acik Kaynak Gelir Modelleri Arastirmasi.md" raporundaki
bulgularin bu projeye uyarlanmis karar halidir. Yasayan belgedir;
kosullar degistikce guncellenir.

## Mevcut durum (v2.0)

- Lisans: **GPL-3.0-or-later** (tek telif hakki sahibi: goun7).
- GPL geregi binary dagitimi ucretli "koltuk lisansina" baglanamaz;
  alan herkes kopyalayip dagitabilir.
- Hedef kitle (Arch/CachyOS kullanicilari) odeme duvarina en direncli
  grup; dogrudan lisans satisi bu asamada ekonomik degil.

## Karar: Bagis katmani + gelecekte Open Core

### Asama 1 — Bagis/sponsorluk (SIMDI, sifir maliyet)

Urun ucretsiz kalir; gonullu destek toplanir:

- [x] `.github/FUNDING.yml` (GitHub Sponsors + Polar + Kreosus)
- [x] About dialoguna "Destek Ol" butonu (`config.DONATE_URL`)
- [x] README destek bolumu
- [ ] **KULLANICI:** GitHub Sponsors hesabini etkinlestir
- [ ] **KULLANICI:** polar.sh/goun7 magaza/destek sayfasini actiflestir
- [ ] **KULLANICI:** kreosus.com/goun7 sayfasini olustur

### Asama 2 — Veri toplama (beta sonrasi)

Indirme sayisi + opt-in geri bildirim ile odeme egilimi olculur.
Karar esigi: ayda 500+ indirme veya 10+ destekci → Asama 3 degerlendirilir.

### Asama 3 — Open Core (yalnizca veri desteklerse)

Cekirdek GPL kalir; **sunucu gerektiren** Pro katmani eklenir:

- Imzali otomatik guncelleme servisi
- Ekip/kurumsal politika profilleri
- Bulut senkronizasyon backend'i (hosted)

Anahtar dogrulama icin kendi sunucusu yerine **Merchant of Record**
kullanilir (Polar.sh birincil aday — TR saticiyi destekler, KDV yukunu
ustlenir). Boylece sunucu satin almak gerekmez.

### Dual licensing (pasif firsat)

Biri pkgforge'u kapali urunune gomup GPL yukumluluklerinden muaf
olmak isterse ticari lisans pazarligi yapilir. Tek katkici goun7
oldugu ve paketteki ucuncu taraf Apache-2.0 GPLv3 ile uyumlu oldugu
icin gelecek surumleri yeniden lisanslama hakki saklidir. Talep
gelmezse kayip sifirdir; ayri altyapı kurulmaz.

## Odeme kanallari ozeti (TR baglamı)

| Kanal | Rol | Durum |
|---|---|---|
| GitHub Sponsors | Birincil, global | Hesap etkinlestirme bekliyor |
| Polar.sh | MoR, lisans anahtari hazir | Sayfa actiflestirme bekliyor |
| Kreosus | TR bagis | Sayfa olusturma bekliyor |
| iyzico | Yurt ici satis (Asama 3) | Planli |

## Hukuki notlar

- GPL altinda "ucretsiz surum + ucretli destek" tamamen yasaldır;
  satilan sey kod degil hizmet/kanaldir.
- Yeniden lisanslama yalnizca GELECEK surumler icin gecerlidir;
  yayinlanmis GPL surumler geri alinamaz.
- Ticari sozlesme/asama-3 oncesi kisa bir avukat gorüşü onerilir.