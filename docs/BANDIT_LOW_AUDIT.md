# Bandit LOW Severity Audit — S3 (güncel)

Tarih: 2026-09-08 · Komut:
`bandit -r core/ ui/ i18n/ cli.py main.py config.py` (CI kapısı `-ll` değil,
tam liste)
Tarihçe: Tur-54'te 43 LOW idi; `core/api/*` bölünmesi ve yeni modüllerle 64 oldu.

## Toplam LOW Issue: 64 (0 Medium, 0 High)

### Kategori Özeti

| Kategori | Sayı | Güvenlik Riski | Aksiyon |
|----------|------|----------------|---------|
| B603: subprocess_without_shell | 23 | Düşük — shell=False kullanılıyor, güvenli | kabul edilebilir |
| B404: subprocess import blacklist | 13 | Bilgilendirme — subprocess kaçınılmaz | false positive, paketleme aracı |
| B101: assert_used | 13 | Bilgilendirme — test + invariant assert'leri | kabul (test kodu +运行时 kontrol) |
| B607: partial executable path | 5 | Düşük — PATH'tan araçlar çağrılıyor | ToolPaths/shutil.which ile doğrulanıyor |
| B110: try_except_pass | 4 | Düşük — cleanup/optional kodlarda | log eklenmeli veya daraltılmalı |
| B105: hardcoded password string | 3 | False positive — boş string/test fixture | kabul |
| B107: hardcoded password funcarg | 2 | False positive — boş string default | kabul |
| B311: random | 1 | Bilgilendirme — `random` kullanımı (güvenlik-dışı) | CI'da skip'li; kabul |

### Detaylı Analiz

#### B603/B404: subprocess Kullanımı (36 issue)
PkgForge bir paket dönüştürme aracıdır; makepkg, pacman, xdelta3, ar, tar gibi
sistem araçlarını çağırmak zorundadır. Tüm subprocess çağrıları shell=False ile
yapılmaktadır (`core/security.py::safe_run`) ve kullanıcı girdisi sanitize
edilmektedir. Beklenen davranış, güvenlik riski yok.

#### B101: assert (13 issue)
Test dosyaları dışındaki assert'ler değişmez (invariant) kontrolleridir;
üretimde `-O` ile koşulmuyor. Kabul.

#### B110: try_except_pass (4 issue)
`core/api/*` içindeki best-effort persistence ve optional cleanup blokları.
Non-critical; log'lu dallar tercih edilir ama mevcut hali kabul.

#### B607: Partial Executable Path (5 issue)
Sistem araçları PATH'tan çağrılıyor; ToolPaths keşfi + `shutil.which`
kontrolleri mevcut. Kabul edilebilir.

#### B105/B107/B311 (6 issue)
Boş-string default'lar, test fixture'ları ve güvenlik-dışı `random`
kullanımı. CI skoru etkilemez (`-ll --skip B101,B311`).

### Sonuç
**0 aksiyon gerekli.** Tüm LOW issue'lar PkgForge'un doğasından kaynaklanan
beklenen uyarılardır. Medium/High severity issue yoktur. CI gate (`-ll`) temizdir.
