# PkgForge — Terim Sözlüğü (Glossary)

Arayüzde ve belgelerde tutarlı terminoloji kullanmak için başvuru kaynağı.
Bir kavram için **tek** karşılık kullanılır; eşanlamlılardan kaçınılır.

## Eylemler

| Kavram | Türkçe | English | Not |
|--------|--------|---------|-----|
| convert | Dönüştür | Convert | Fiil (buton). İsim: "Dönüşüm" / "Conversion" |
| install | Kur | Install | Buton. İsim: "Kurulum" / "Installation" |
| uninstall / remove | Kaldır | Remove / Uninstall | Yıkıcı eylem |
| rollback | Geri al | Roll back | İsim: "Geri alma" |
| build | Derle | Build | AUR'dan paket derleme |
| search | Ara | Search | |
| refresh | Yenile | Refresh | Listeyi tazeleme |
| save | Kaydet | Save | |
| enable | Etkinleştir | Enable | |
| disable | Kapat | Disable | "Devre dışı bırak" kullanılmaz |
| scan | Tara | Scan | |
| verify | Doğrula | Verify | İmza doğrulama |
| compare | Karşılaştır | Compare | |
| audit | Denetle | Audit | İsim: "Denetim" |
| export | Dışa aktar | Export | Kart başlıklarında "Export" kalabilir |
| cancel | İptal | Cancel | |
| start | Başlat | Start | |
| copy path | Yolu kopyala | Copy path | |
| open folder | Klasörü aç | Open folder | |

## Durumlar

| Kavram | Türkçe | English |
|--------|--------|---------|
| success | Başarılı | Success |
| failed | Başarısız | Failed |
| pending | Beklemede | Pending |
| running | Çalışıyor | Running |
| cancelled | İptal edildi | Cancelled |
| active | Aktif | Active |
| inactive / passive | Pasif | Inactive |
| enabled | Etkin | Enabled |
| disabled | Devre dışı | Disabled |
| installed | Kurulu | Installed |
| ready | Hazır | Ready |
| missing | Yok | Missing |
| clean | Temiz | Clean |
| offline | Çevrimdışı | Offline |
| out-of-date | Eski | Out-of-date |

## Kavramlar (değişmez / çevrilmeyen)

| Terim | Açıklama |
|-------|----------|
| SBOM | Software Bill of Materials — çevrilmez |
| Provenance | Paket köken kaydı — çevrilmez |
| Sigstore / cosign | İmza altyapısı — çevrilmez |
| CVE | Common Vulnerabilities and Exposures — çevrilmez |
| OCI | Open Container Initiative — çevrilmez |
| AUR | Arch User Repository — çevrilmez |
| Delta update | Delta güncelleme — başlıkta "Delta" korunur |
| Snapshot | Anlık görüntü — UI'da "Snapshot" korunur |
| Fleet | Filo yönetimi — başlıkta "Fleet" korunur |
| Plugin | Eklenti — UI'da "Plugin" korunur |
| PKGBUILD | Arch paket tarifi — çevrilmez |

## Biçim kuralları

- **Butonlar** emir kipiyle: "Dönüştür", "Kur", "Tara" (fiil).
- **Kart başlıkları** isim öbeğiyle: "Dönüştürme", "Güvenlik Paneli".
- **Durum rozetleri** kısa sıfat/fiilimsi: "Başarılı", "Çalışıyor".
- Teknik dosya yolu örnekleri (`/yol/paket.rpm`) çevrilmez.
- Dil adları kendi dilinde gösterilir: "Türkçe", "English".
- Klavye kısayolları: `Ctrl+K` (komut paleti), `Alt+1..9` (sayfa geçişi).
