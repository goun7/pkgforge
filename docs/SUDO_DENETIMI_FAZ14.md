# PkgForge — Faz 14: Sudo/Pkexec Bombardımanı Kök-Neden Analizi ve Çözümü

> **Belirti:** Kullanıcı ekranında bir işlem sırasında art arda yağan parola
> diyalogları ("bolca sudo isteği").

## Kök Nedenler (kanıtlı)

### N1 — Gerçek polkit policy'si hiçbir yere kurulmuyordu (KRİTİK)
`packaging/polkit/org.pkgforge.helper.policy` (doğru action id'leri:
`org.pkgforge.install`, `org.pkgforge.delta-update`,
`org.pkgforge.snapshot-cleanup`; `auth_admin_keep` yetkileri) TAMAMEN
ölü bir varlıktı: `pyproject.toml` data-files'a girmiyordu, `install.sh`
kurmuyordu, PKGBUILD değmiyordu. Yalnızca `data/org.pkgforge.app.policy`
kuruluyordu — ki o da **farklı bir action id**'si (`org.pkgforge.app.install`)
ve yalnızca `pkexec pacman` fallback'iyle eşleşiyor.
Sonuç: her helper çağrısı polkit'in genel `org.freedesktop.policykit.exec`
action'ına düşüyor → **her çağrıda ayrı parola penceresi**.

### N2 — Tek işlemde 4-5 ayrı pkexec çağrısı (KRİTİK)
Delta otomatik güncellemeyi kurmak için: script yaz + chmod + service yaz +
timer yaz = **4 ayrı diyalog**; snapshot temizliği aynı desen; ayrıca
daemon-reload/enable/start için 3 yetkisiz systemctl çağrısı (bkz. N3).
Diyaloglar saniyeler içinde art arda açılınca "bombardıman" deneyimi
oluşuyordu.

### N3 — systemctl fiilleri yetkisiz çağrılıyordu (KRİTİK, sessiz başarısızlık)
`daemon-reload`/`enable`/`start`/`stop`/`disable` çağrıları
`[systemctl, ...]` ile **yetkisiz** gidiyordu; sistem birimleri için bunlar
root ister → returncode kontrolü de yapılmadığından sessizce başarısız
oluyordu. Kullanıcı "çalışmadı" diye tekrar tekrar butona basınca diyalog
serileri katlanıyordu.

### N4 — Timer aralığı yok sayılıyordu (ORTA)
Kullanıcı 12 saat seçse de timer birimi sabit `OnCalendar=00/6`
üretiyordu — `interval_hours` yalnızca açıklama metnine giriyordu.

### N5 — app.policy her seferinde soruyordu (ORTA)
Fallback action'ı `auth_admin` (oturum boyunca her kurulum ayrı parola).

## Düzeltmeler

| # | Değişiklik | Dosya |
|---|-----------|-------|
| D1 | `write-batch` alt-komutu: NUL-ayırıcılı manifest ile **TÜM dosyalar tek pkexec diyalogunda** | `scripts/pkgforge-privileged.sh` |
| D2 | `build_write_batch_manifest()` + `privileged_write_batch_argv()` | `core/privileged.py` |
| D3 | Delta kurulumu: 3 dosya + chmod tek write-batch'te; enable/start helper üzerinden yetkili; hata kodu yüzeye çıkar | `core/delta_updater.py` |
| D4 | Delta kaldırma + enable/disable sarmalayıcıları: systemctl fiilleri helper üzerinden | `core/delta_updater.py` |
| D5 | Snapshot temizlik kur/kaldır: aynı tek-diyalog akışı | `core/snapshot_cleanup.py` |
| D6 | Timer: `interval_hours` artık takvime işliyor (bölenlerde OnCalendar adımı, değilse OnUnitActiveSec) | `core/delta_updater.py` |
| D7 | API kurulum rotası doğrudan `pkexec pacman` yerine konsolide helper `install-pkg` rota'ya geçti | `core/api_server.py` |
| D8 | **Gerçek helper policy artık kuruluyor**: pyproject data-files + install.sh | `pyproject.toml`, `scripts/install.sh` |
| D9 | Helper betikleri `/usr/share/pkgforge/scripts/`'e root-0755 kuruluyor (polkit root-dışı betiği reddeder) | `scripts/install.sh` |
| D10 | Fallback policy `auth_admin_keep`'e çekildi | `data/org.pkgforge.app.policy` |
| D11 | GUI mesajlarından "sudo systemctl … yap" yönlendirmeleri kaldırıldı (uygulamanın kendi kaldır akışı var) | her iki modül |

## Kullanıcı İçin Sonuç
- Kurulu bir sistemde ilk kurulumdan sonra alpha opsiyonu olan polkit kuralı
  devrede: bir işlem ↔ **tek parola**, sonraki ~5 dk boyunca hatırlanır.
- Delta/snapshot kurulumları: eskiden 4-5 diyalog → **1 diyalog** (+ yetkili
  enable zinciri artık gerçekten çalışıyor).
- Kurulum aralığı seçimi artık davranışı değiştiriyor.

## Doğrulama
- Hedefli: delta/snapshot unit testleri 29/29 (yeni: `tek write-batch`,
  `timer aralık yansıması`, ret-kod yüzey testleri).
- api install rotası + helper testleri 23/23.
- `bash -n` her iki kurulum betiği OK; her iki policy XML parse OK.
- ruff/mypy temiz; tam pytest rc=0 (bkz. progress kaydı).
