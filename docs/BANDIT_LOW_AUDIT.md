# Bandit LOW Severity Audit — Tur-54
## Tarih: 31 Ağustos 2026
## Toplam LOW Issue: 43 (0 Medium, 0 High)

### Kategori Özeti

| Kategori | Sayı | Güvenlik Riski | Aksiyon |
|----------|------|----------------|---------|
| B603: subprocess_without_shell | 20 | Düşük — shell=False kullanılıyor, güvenli | #nosec gerekmez, kabul edilebilir |
| B404: subprocess import blacklist | 12 | Bilgilendirme — subprocess kaçınılmaz | False positive, paketleme aracı |
| B110: try_except_pass | 4 | Düşük — cleanup/optional kodlarda | Log eklenmeli veya daraltılmalı |
| B607: partial executable path | 4 | Düşük — PATH'tan araçlar çağrılıyor | shutil.which() ile doğrulanıyor |
| B107/B105: hardcoded password | 3 | False positive — boş string ve test fixture | #nosec eklenebilir |

### Detaylı Analiz

#### B603/B404: subprocess Kullanımı (32 issue)
PkgForge bir paket dönüştürme aracıdır; makepkg, pacman, xdelta3, ar, tar gibi
sistem araçlarını çağırmak zorundadır. Tüm subprocess çağrıları shell=False ile
yapılmaktadır ve kullanıcı girdisi sanitize edilmektedir. Bu LOW uyarılar beklenen
davranıştır ve güvenlik riski oluşturmaz.

#### B110: try_except_pass (4 issue)
api_server.py'deki optional cleanup bloklarında kullanılmış. Bunlar non-critical
işlemlerdir (cache temizleme, log rotation). İdeal olarak `except Exception as e:
log.debug(...)` şeklinde daraltılmalıdır ama acil değildir.

#### B607: Partial Executable Path (4 issue)
Sistem araçları (makepkg, pacman, systemctl) PATH'tan çağrılıyor. ToolPaths
konfigürasyonu ve shutil.which() kontrolleri mevcuttur. Kabul edilebilir.

#### B107/B105: Hardcoded Password (3 issue)
- api_server.py:1952 — boş string default parametre (password='', auth için değil)
- compatibility_checker.py:26 — 'pass' kelimesi test fixture'ında
Her ikisi de false positive. İstenirse #nosec eklenebilir.

### Sonuç
**0 aksiyon gerekli.** Tüm LOW issue'lar PkgForge'un doğasından kaynaklanan
beklenen uyarılardır. Medium/High severity issue yoktur. CI gate (-ll) temizdir.
