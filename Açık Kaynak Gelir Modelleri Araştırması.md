Hizmet almadan destek olmak isteyen biri için ayrı bir kripto hesabına **kesinlikle gerek yoktur**. Bankadaki GVK Mükerrer 20/B istisna hesabına kripto borsasından (Binance TR vb.) aktaracağın Türk Lirası tutarından banka kaynak sorgulamadan **otomatik %15 stopaj** keser. Terminolojide "bağış" yerine "Bireysel Sponsor / Backer" dediğin sürece para 2860 Sayılı Kanun takibine takılmaz ve %100 yasal ticari kazanç sayılır.

Aşağıdaki Markdown dokümanı, kurguladığımız en iyilenmiş mimarinin, yasal uyum adımlarının ve otomasyon kodlarının eksiksiz ve nihai özetidir. Dosyayı doğrudan `.md` olarak kaydedip kullanabilirsin.

---

# **Sıfır Sunucu Maliyetli Global Yazılım Satış, Lisanslama ve Vergi Uyum Rehberi**

## **1. Hukuki ve Mali Uyum Mimarisi (Türkiye Mevzuatı)**

Türkiye merkezli bir geliştirici olarak şirket kurmadan, fatura kesmeden ve muhasebeci tutmadan global satış yapmak için aşağıdaki yasal sınırlar belirlenmiştir:

* **Vergi İstisnası (GVK Mükerrer 20/B):** Gelir İdaresi Başkanlığı'nın (gib.gov.tr) Dijital İçerik Üreticiliği ve Yazılım Geliştirici İstisnası kapsamında bankada açılan özel ticari hesaba gelen tüm paralardan banka otomatik **%15 gelir vergisi stopajı** keser. Bu işlem yıllık 5.3M TL limite kadar başka hiçbir beyanname veya KDV yükümlülüğü getirmez.


* **2860 Sayılı Yardım Toplama Kanunu Koruması:** İzinsiz bağış toplama cezalarından korunmak için projede kesinlikle **"Donate / Bağış / Yardım"** terimleri kullanılmaz. Tüm ödeme kanallarında **"Sponsor / Backer / Commercial License / Access Tier"** ifadeleri tercih edilir.



---

## **2. Ödeme ve Satış Kanalları Matrisi**

| Kanal Türü | Platform | İşlem / Platform Ücreti | Türkiye Payout (Aktarım) Mimarisi | Kullanım Senaryosu |
| --- | --- | --- | --- | --- |
| **Birincil Fiat (Kart)** | **Polar.sh** | %5 + $0.50

 | Stripe Connect Express $\rightarrow$ TR IBAN

 | B2B/B2C Lisans satışı, küresel KDV & Fatura yönetimi (MoR).

 |
| **Topluluk Desteği** | **GitHub Sponsors** | %0 (Bireysel)

 | Stripe Connect $\rightarrow$ TR IBAN

 | Repoyu desteklemek isteyen geliştiriciler ve kurumlar.

 |
| **Kripto (Hazır Checkout)** | **Hel.io** | %0.75 - %1.00 | On-Chain Wallet $\rightarrow$ Binance TR $\rightarrow$ 20/B IBAN

 | Web3 / Solana / EVM kullanıcılarına hızlı checkout bağlantısı.

 |
| **Kripto (B2B Stablecoin)** | **Spherepay.co** | API Tabanlı Kademeli | On-Chain Wallet $\rightarrow$ Binance TR $\rightarrow$ 20/B IBAN | Kurumsal USDT/USDC B2B ödeme altyapısı. |
| **Kripto (Aracısız / %0)** | **Helius.dev** | %0 Platform Ücreti | On-Chain Wallet $\rightarrow$ Binance TR $\rightarrow$ 20/B IBAN

 | Solana cüzdan adresine gelen transferleri RPC Webhook ile dinleme.

 |

---

## **3. Otomatize Lisanslama Akışı (Cloudflare Worker)**

Müşteri hangi kanaldan (Polar, Hel.io veya Helius) ödeme yaparsa yapsın, sistemi otomatize eden sunucusuz mimari şudur:

```
[Müşteri Ödemesi (Kart veya Kripto)]
                  │
                  ▼ (Webhook Trigger)
   [Cloudflare Worker (Serverless)]
                  │
                  ├─► 1. On-Chain / API Ödeme Doğrulaması
                  ├─► 2. Ed25519 İmzalı 'license.jwt' Üretimi
                  └─► 3. Resend API İle E-Posta Gönderimi

```

---

## **4. GitHub Repo Yapılandırması**

### **.github/FUNDING.yml**

```yaml
github: [kullanici_adi]
polar: [kullanici_adi]
custom: ["https://hel.io/pay/[urun_id]"]

```

### **README.md Yasal Uyum Metni**

```markdown
## Commercial Licensing & Sponsorship

This software is distributed under Fair Source / Open Core terms. 

* **Commercial License:** Required for enterprise usage and advanced modules.
  * [Purchase via Credit Card (Polar.sh)](https://polar.sh/kullanici_adi/products/...)
  * [Purchase via Crypto (Hel.io)](https://hel.io/pay/...)
* **Community Sponsorship:** Support ongoing development as a backer.
  * [Sponsor on GitHub](https://github.com/sponsors/kullanici_adi)

```

---

## **5. Adım Adım Uygulama Planı**

1. **GVK 20/B Başvurusu:** Dijital Vergi Dairesi (`gib.gov.tr`) üzerinden "Uygulama Geliştiriciliği İstisna Dilekçesi" ver ve onaylı belge ile bankada özel hesabını aç.


2. **Polar.sh Kurulumu:** Polar hesabı açıp Stripe Connect Express üzerinden 20/B hesabının IBAN'ını bağla.


3. **Kripto Altyapısı:** `hel.io` veya `helius.dev` üzerinde ödeme linkini / webhook'unu yapılandır.


4. **Cloudflare Worker Dağıtımı:** Webhook gelen ödemelere karşılık Ed25519 imzalı JWT lisansı üreten koda API anahtarlarını ekleyip deploy et (`npx wrangler deploy`).


5. **Yazılıma Lisans Doğrulayıcı Ekleme:** Rust/Python/Go ile yazılmış uygulamana çevrimdışı doğrulamayı destekleyen Public Key kontrol kodunu ekle.
