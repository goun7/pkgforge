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

## 2026-10-16 — tek-örnek (single-instance) kilidi: ÇÖZÜLDÜ (olay değil, kuyruk kanalı)

**Önceki davranış:** uygulama açıkken ikinci "Birlikte aç" yeni kabuk + yeni
`main.py serve` sidecar'ı açıyordu (ölçüldü: 2 sidecar süreci).

**İlk deneme ve neden bırakıldığı:** `tauri-plugin-single-instance` + özel
webview olayı (`pkgforge://open-files`, sonra `app/open-files`). Kilit
çalışıyordu (ikinci süreç çıkıyor, ikinci sidecar doğmuyor, pencere öne
alınıyor) ve `emit` **Ok** dönüyordu — hem plugin'in soket thread'inden hem
`run_on_main_thread` ile ana thread'den — ama üç ayrı derlemede de webview
tarafı hiç tepki vermedi. Yalıtılmış ölçüm: aynı olayı açılıştan 6 sn sonra
zamanlayıcıyla gönderdik, `emit` yine `Ok`; JS tarafı kanıtlı bir RPC
(`queue.add`) çağırdığında bile `queue.db`'de satır oluşmadı. Yol politikası
kontrolü aynı path için `izinli` döndü, yani reddedilmiş değildi. Yarım
çalışan kilit ikinci dosyayı **sessizce düşüreceği** için geri alındı.

**Çözüm (şu an shipped):** dosyalar webview'a değil, doğrudan sidecar RPC'sine
devredilir — `sidecar::queue_files()` → `queue.add` → kalıcı `queue.db`; pencere
öne alınır ve masaüstü bildirimi gönderilir ("kuyruğa eklendi (N)"). Böylece
kullanıcının görmesi koşullu değildir: kayıt diskte, Toplu sekmesinden
başlatılır, süreç kapanSA bile `restore_queue` ile geri gelir.

**Gerçek çift çalıştırma ölçümü (fix sonrası):**
- ikinci örnek öncesi/sonrası: `kabuk=1 sidecar=1` (ikinci doğmuyor),
- ikinci sürecin logu 1 satır (derhal çıkıyor),
- instance-1 logu: `pkgforge: ikinci örnek dosyaları kuyruğa eklendi:
  {"result":{"added":1}}`,
- `queue.db`: `{'id':'q1','path':'/tmp/pf_si5/ikinci.deb','status':'pending'}`.

Ayrıca `rust-version` 1.77 → **1.90** (plugin'in alt sınırı; beyan artık gerçeği
yansıtıyor).

**Açık kalan tek şey (ölçüldü, kökü bilinmiyor):** Rust→JS *özel* olayları bu
derlemede webview dinleyucusuna ulaşmıyor. Yanıltıcı olmasın: sidecar'ın
`event/*` itmelerinin JS'e ulaştığını **kanıtlamadık** — mekanizma aynı
`app.emit` çağrısı olduğundan şüphe orada da; bugüne dek hiçbir test bunu uçtan
uça doğrulamamış (vitest'te `listen` mock'lu, visual-qa ise Tauri'suz tarayıcıda
koşuyor). Çözüm için debug derlemesi + WebKit inspector oturumu gerekiyor;
UI'yi canlı tutan tek yol bu olduğu için kalıcı bir TODO olarak bırakıldı
(`docs/DEAD_CODE_AUDIT.md` → "Bilinmeyen").

## 2026-10-16 — QueueStore thread hatası: kuyruk hiç kalıcı değildi (bulundu + düzeltildi)

Kuyruk devrini ölçerken çıktı: `queue.add` yanıtı `{"added": 1}` dönüyor, ama
`queue.db` boş kalıyordu. Neden iki katmanlı:

1. `QueueStore` bağlantısı `sqlite3.connect()` **`check_same_thread=False`
   olmadan** kuruluyordu; sidecar istekleri worker thread'lerde koştuğu için her
   `upsert` `sqlite3.ProgrammingError` atıyordu (doğrudan ölçüm: worker'da
   upsert → `ProgrammingError`, satır sayısı 0).
2. `handlers_queue._persist_item()` hata `except Exception: pass` ile
   yuttuğu için bu, bir ay boyunca görünmezdi.

Düzeltme: paylaşımlı bağlantı + tüm işlemleri saran `threading.Lock`; yutma
yeri `logging.warning` ile gözlenebilir yapıldı. Kalıcı kilit:
`tests/test_queue_store_threading.py` (3 test; düzeltme öncesi 3/3 KIRMIZI
oldukları üretildi — worker upsert, 8 thread eşzamanlı yazım, remove/clear).

## 2026-10-16 (ikinci tur) — GUI bir aylık BAYAT motor çalıştırıyormuş

Kullanıcı `sudo ./scripts/install.sh` sonrası kurulumu doğrularken ölçüldü:

| Gözlem | Kanıt |
|---|---|
| Kurulu kabuk, yanındaki gömülü sidecar'ı seçiyor | `ps`: `/usr/lib/pkgforge/desktop/pkgforge-sidecar serve` |
| O sidecar 17 Eylül'de derlenmiş (101 MB) | `ls -la` mtime `Eyl 17 17:10`; düzeltmeler 14–16 Ekim commit'lerinde |
| Sonuç: CLI taze kodu, GUI bir aylık motoru çalıştırıyordu | `/usr/lib/pkgforge/main.py` aynı gün kopyalanmış, `pkgforge-sidecar` değil |

Üç katmanlı düzeltme (hepsi ayrı ayrı gerçek çalıştırmayla doğrulandı):

1. `main.py::_launch_desktop`: kabuk bu kurulum ağacının **içindeyse**
   `PKGFORGE_SIDECAR=python` zorunlu; `PKGFORGE_PYTHON` yoksa CLI'yi çalıştıran
   interpreter'ın kendisi veriliyor. Taklit `/usr/lib` düzeninde dönüşüm canlı
   ağaçtan koştu, gömülü sidecar'ın imzası log'da 0.
2. `sidecar.rs::bundled_sidecar_fresh()`: kabuk **doğrudan** çalıştırılsa bile
   (terminal, harness, paket bağıntısı) gömülü snapshot kurulu Python kodundan
   eskiyse kullanılmıyor ve sebebi stderr'e yazılıyor. İki yönlü ölçüm: bayat
   snapshot → `bundled sidecar kurulu Python kodundan daha eski; canli Python
   sidecar'i kullaniliyor`; taze snapshot → işaret yok, gömülü kullanılıyor.
3. `install.sh`: snapshot Python ağacından eskiyse artık kopyalanmıyor, daha
   önce kopyalanmış olan kaldırılıyor (101 MB bayat motor sistemde kalmıyor).

Aynı turda bulunan ikinci gerçek hata: **kabuk doğrudan çalıştırılınca
çöküyordu**. Wayland'da `Gdk-Message: Error 71 (Protocol error) dispatching to
Wayland display`, `GDK_BACKEND=x11` zorlanırsa `Failed to initialize GTK` +
SIGABRT. DMABUF ayarı yalnızca launcher ortamındaydı; artık kabuk kendi
içinde koyuyor (`main.rs`, çağıranın değeri varsa ona dokunmadan). Aynı
nedenle `desktop/scripts/e2e-integration.sh`'teki sabit `GDK_BACKEND=x11`
kaldırıldı (Wayland oturumunda GTK'yi düşürüyordu); harness artık bu makinede
**E2E: ALL CHECKS PASSED** veriyor.

`desktop/scripts/e2e-integration.sh` ölü dosya denetiminde "yalnızca eski bir
plan belgesinde geçiyor" diye işaretlenmişti; içeriği gerçek bir UÇTAN UCA
doğrulaması (kabuk + sidecar + JSON-RPC + temiz kapanış) ve CI başsız olduğu
için çağırıyor — **silinmedi**, ilk kez koşularak yeşile getirildi.

## Kalan insan adımları (ölçülmüş durum, 2026-10-16 gecesi)

1. **Yeni etiket gerekir — v2.2.0 bugünkü düzeltmeleri İÇERMİYOR.**
   `v2.2.0` tarball'ının sha256'sı bugün yeniden indirilip doğrulandı
   (`1b4639c8…`, 4 174 629 bayt — root `PKGBUILD` iddiası DOĞRU), ama tarball
   17 Eyl kodudur: modern UI yönlendirmesi, argv aktarımı, Qt parent düzeltmesi,
   kuyruk kalıcılığı ve Tauri 2.12 bu etikette yok. Yani stable `pkgforge`
   AUR paketi bugün kurulsa bayat GUI davranışını taşır. Çözüm: `v2.2.1`
   etiketi + root PKGBUILD'de `pkgver/sha256sums` yenilemesi (geri
   döndürülemez/ethkî adım olduğu için kullanıcı onayı beklenir).
2. AUR gönderimi: `pkgforge-git` PKGBUILD'i bugün **gerçekten derlendi**
   (`makepkg -f --noconfirm --skipinteg`, exit 0 → 18,9 MB paket;
   `usr/lib/pkgforge/desktop/{pkgforge-desktop, pkgforge-sidecar}` pakette).
   `namcap`: **0 hata, 471 uyarı** — uyarıların 454'ü namcap'ın kendi modüllerimizi
   ("core.*", "ui.*") dış bağımlı sanması, kalanı tipik sezgisel notlar.
   Temiz chroot koşumu (`extra-xdg-build`) ayrıca denenmedi; sudo/chroot ister.
3. Release CI: `v2.2.0` etiketi için koşan işler yeşildi; yeni etikette tekrar
   izlenmeli.
4. debtap parite tablosunun debtap sütunu (`docs/BENCHMARK_PARITY.md` —
   root `debtap -u` gerektirir).
5. Bilinen tek kökü-bulunamayan davranış: kabuğun Rust→JS özel olayları webview
   dinleyucusuna ulaşmıyor (bkz. yukarıdaki "tek-örnek" bölümü ve
   `docs/DEAD_CODE_AUDIT.md` → "Bilinmeyen"). Kullanıcıya görünür etkisi
   bilinemiyor; bu yüzden UI canlı güncellemeleri de doğrulanmış sayılmıyor.

## Bu geceki temizlik (disk)

- `build/` (113 MB PyInstaller iş dizini) ve `dist/` (98 MB kopya yan ürün)
  silindi; yerlerine **güncel koddan** taze sidecar üretildi
  (`bash desktop/scripts/build-sidecar.sh`, 102 MB, Eki 16 23:05) ve gerçek
  JSON-RPC ile denendi: `app.doctor` → `"version": "2.2.0"`,
  `"exec_path_pinned": true` (bu oturumun düzeltmesi içinde → bayat değil).
- `install.sh` tazelik kapısı artık aynı dosya için `TAZE` diyor, yani bir
  sonraki kurulumda sisteme gidecek sidecar güncel kod olacak.
