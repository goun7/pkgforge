# PkgForge v2.2.0 — Sürüm Hazırlık Durumu

> Son doğrulama: 2026-09-17 · `make verify` + `pnpm test` + gerçek
> `pkgforge desktop` açılış duman testi (bu makine)
> Tarihsel notlar `docs/RELEASE_READINESS.md` (v1.1.0 dönemi) ve git
> geçmişindedir; bu dosya tek güncel kaynaktır.

## Ölçülen Gerçek Durum

| Alan | Durum | Kanıt |
|---|---|---|
| Test suit'i | **2582 toplanan: 2577 passed, 4 skipped, 0 failed** | `make verify` (2026-09-17) |
| Kapsama | **%99.61** — 12 835 ifade, 50 eksik (`core/`+`ui/`+`i18n/`) | `--cov-fail-under=99` geçiyor |
| mypy --strict | **0 hata** (core+cli+main+config+ui) | `make verify` |
| ruff | **0 hata** (CI-parite) | `ruff check .` |
| bandit | **temiz** (`-ll`, core+entry points; 0 Medium/0 High) | `make verify` |
| Desktop (TS) | **582/582 vitest, tsc 0 hata** | `cd desktop && pnpm test` |
| Masaüstü ikilisi | **gerçek derleme + açılma** (sidecar + `tauri build`) | `pkgforge desktop` 15 sn çalıştı |
| i18n | **993/993** tr/en parite; CLI kullanıcı-yolu tam çeviri | `tests/test_i18n_parity.py` |
| pip-audit | temiz | CI `supply-chain` job'u |
| Repo | **PUBLIC**, master korumalı (force-push/silme yasak) | `gh repo view` |
| Release boru hattı | gate (ruff+mypy+bandit+tam suit) → build → SBOM (SPDX+CycloneDX) + SLSA provenance + SHA256SUMS | `release.yml` |

## Bilinen başarısızlık: yok (2577 passed + 4 skipped, 0 failed)

Eskiden "pre-existing" sanılan 2 delta-timer testi bayat mock çıktı
(Faz-14 argv değişimine uyarlandı); ubuntu CI'daki kalan farklar
araç-guard'larıyla kapatıldı. CI yeşili release boru hattında izlenir.

## 2026-09-17 denetim: "100/100" değildi; açılmama nedenleri ve düzeltme

Kullanıcının "açılmıyor" bildiriminin kök nedenleri (hepsi komutla kanıtlandı):

1. `/usr/local/bin/pkgforge` wrapper'ı eski `~/Masaüstü/pkgforge` yolunu
   içeriyordu (proje taşınmıştı) → `python3: can't open file ...` (exit 2).
2. `.venv` eski konumda yaratıldığı için tüm konsol betikleri (pip, pytest,
   mypy, bandit) kırık shebang'e sahipti → yerinde 31 betik onarıldı.
3. Tauri ikilisi ve sidecar **hiç derlenmemişti**: `externalBin` yolu
   `binaries/pkgforge-sidecar-<triple>` eksik olduğundan `tauri build`
   "resource path doesn't exist" ile çakılıyordu.
4. Menü girişi `Exec=pkgforge gui` ile donmuş PyQt6 arayüzünü açıyordu;
   birincil arayüz (Tauri) menüden açılamıyordu.

Düzeltmeler: `pkgforge desktop` alt komutu (ikili yoksa nedeni söyleyip
klasik arayüze düşer; `data/pkgforge.desktop` artık onu çağırıyor) +
`install.sh` hazır Tauri ikilisini sistem kurulumuna kopyalıyor.

### Kalan insan adımı (sudo gerekir, otomatik yapılmadı)

```bash
sudo ./scripts/install.sh   # wrapper + menü girişi + ikili tazelenecek
```

Beklenirken: `~/.local/bin/pkgforge desktop` modern arayüzü açar (kaynak
ağacında `desktop/src-tauri/target/release/pkgforge-desktop` derlenmiş durumda,
`_find_desktop_binary()` onu buluyor).

## 2026-10-16 — menü girişi açıyordu ama dosyayı görmüyordu

Kullanıcı şikâyeti: "qoder'ı pkgforge ile yükseltirken eski arayüz çıktı".
İki ayrı gerçek hata bulundu:

1. **Tauri ikilisi makinede hiç yoktu.** `install.sh` ikiliyi yalnızca
   `desktop/src-tauri/target/release/pkgforge-desktop` varsa kopyalıyor; o
   dizin silindiği için kurulum sessizce PyQt6'ya düşmüştü. İkili yeniden
   derlendi (`pnpm tauri build --no-bundle`), 4 Rust testi + 591 vitest testi
   ve tam `make verify` geçtikten sonra kaynak ağacına yerleştirildi.
2. **`Exec=pkgforge desktop %f` dosyayı çöpe atıyordu.** Ne Rust kabuğu argv'yi
   okuyor ne de frontend soruyordu; "Birlikte aç" hiçbir şey yüklenmeden pencere
   açıyordu. Kabuk artık `initial_files` komutuyla yalnızca *gerçekten var olan*
   dosyaların mutlak yollarını veriyor, Convert sayfası açılışta onları kuyruğa
   alıyor. Kanıt: `pkgforge --file …/gelip.deb` izole HOME'da koştu, sidecar
   log'unda `Pipeline başlatıldı: gelip.deb` ve `✓ Dönüşüm tamamlandı` görüldü.

Aynı çalıştırma bir Qt hatası daha ortaya çıkardı (`Cannot create children for a
parent that is in a different thread`): sidecar pipeline'ı main thread'te kurup
worker thread'te çalıştırıyor, `Converter(self._tools, self)` ise Qt parent
istiyor. `_qt_parent()` artık thread farklıysa `None` döndürüyor; nesne ömrü
`self._deb_converter` / `self._installer` alanlarındaki Python referanslarıyla
garantili. `tests/test_pipeline_qt_parent.py` hem davranışı hem de `(..., self)`
deseninin geri gelmesini engelleyen AST anahtarını içeriyor.

### ZERON kapısı (AGENTS.md'in zorunlu kıldığı) — ölçülen durum

`npx zeron scan .` (2026-09-17): **132 sağlıklı buton, 0 uyarı, 4 CRITICAL**.
4 CRITICAL'in tamamı `core/http_assets/swagger/swagger-ui-bundle.js`
içinde (third-party, Apache-2.0, minified) ve "empty stub" olarak
işaretlenen yerler minified fonksiyon gövdeleridir (`function Bf(){}`) —
Swagger UI'nın kendi iç yapısı, bizim kodumuz değil.

| Bulgu | Sınıf | Açıklama |
|---|---|---|
| 4× `swagger-ui-bundle.js` "boş onClick" | **yanlış pozitif** | vendored third-party minified JS; araç `function Bf(){}` gövdelerini bizim boş handler'ımız sanıyor |
| `DropZone.tsx` loading guard | **gerçek, giderildi** | `busy` ref'ti; `useState` + `aria-busy`/`aria-disabled` + meşgulken odaktan çıkma. Düzeltmeden sonra uyarı sayısı 0'a düştü |

ZERON'un third-party varlıklar için dışlama mekanizması yoktur
(yalnızca `--json` / `--exclude-fixtures`); bu yüzden "scan tam temiz"
hedefi araç desteği olmadan sağlanamaz. CDN'e taşımak çevrimdışı
kullanımı bozacağı için yapılmadı. Gerçek bulgu giderilmiştir;
kalan 4 bulgu yukarıda kanıtıyla yanlış pozitiftir.

## 2026-10-16 — denenip GERİ ALINAN: tek-örnek (single-instance) kilidi

**Bilinen davranış (hâlâ böyle):** uygulama açıkken ikinci bir pakete
"Birlikte aç" denirse **yeni bir kabuk + yeni bir `main.py serve` sidecar'ı**
başlıyor (ölçüldü: 2 sidecar süreci). Dosya yine dönüştürülüyor, yani kullanıcı
verisi kaybolmuyor; bedeli ikinci pencere + ikinci sidecar.

**Denenen çözüm:** `tauri-plugin-single-instance` 2.5.4 + `app/open-files`
olayıyla dosyaları çalışan pencereye iletme (Convert sayfası kuyruğa ekliyor;
vitest'te 4/4 yeşil, kırmızı-yeşil doğrulaması yapıldı).

**Gerçek çift çalıştırma ölçümü (3 ayrı derleme ile tekrarlandı):**
- kilit çalışıyor: ikinci süreç çıkıyor, **ikinci sidecar açılmıyor**, pencere
  öne alınıyor;
- kabuk callback'i koşuyor (`dosya sayisi=1` izi), `emit` **Ok** dönüyor — hem
  plugin'in soket thread'inden hem `run_on_main_thread` ile ana thread'den;
- **ama webview hiç tepki vermiyor**: sidecar log'unda ikinci dosya için
  `Pipeline başlatıldı` satırı yok (olay adı `pkgforge://open-files` iken de,
  `app/open-files` iken de aynı). Sidecar'ın kendi `event/finished` yolu JS'e
  ulaşıyor, yani mekanizma kanıtlı; fark bu olayda.

**Neden geri alındı:** yarım çalışan kilit, ikinci dosyayı **sessizce düşürür** —
bugünkü "iki pencere ama dönüştürülüyor" davranışından daha kötü (veri kaybı).
Ayrıca plugin `rust-version = 1.90` istiyor; depoda beyan edilen taban 1.77
(iddiayı doğrulamak için MSRV yükseltmesi gerekecek).

**Sonraki adım adayı:** debug derlemesiyle WebKit inspector'ında JS tarafında
olayın gelip gelmediğine bakmak; geliyorsa `addPaths` çağrısını, gelmiyorsa
Rust→JS olay kanalı farkını (yanıt/anabilen) karşılaştırmak.

## Kalan insan adımları

1. `v2.2.0` tag → release CI izlenir
2. Root `PKGBUILD` sha256 güncellenir (tag tarball'ından)
3. AUR: `pkgforge-git` (hazır, namcap-temiz) + `pkgforge` (stable) gönderimi
   — AUR hesabı + ssh anahtarı gerekir
4. debtap parite tablosunun debtap sütunu (`docs/BENCHMARK_PARITY.md` —
   root `debtap -u` gerektirir)
