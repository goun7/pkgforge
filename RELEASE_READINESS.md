# PkgForge v2.2.0 — Sürüm Hazırlık Durumu

> Son doğrulama: 2026-09-17 (aşağıdaki özet tablo) + 2026-10-16 gece koşusu
> (tarih bölümleri) · `make verify` + `pnpm test` + gerçek `pkgforge desktop`
> açılış duman testi (bu makine)
> Tarihsel notlar `docs/RELEASE_READINESS.md` ve `docs/RELEASE_READINESS_v1.1.0.md`
> (v1.1.0 dönemi; her ikisi de "tarihsel anlık görüntü" olarak etiketlidir) ve
> git geçmişindedir; bu dosya tek güncel kaynaktır.

## Ölçülen Gerçek Durum — **2026-09-17 ölçümü; README'nin 2026-10-16 ölçümü tarafından geçersiz kılındı**

> Aşağıdaki tablo **2026-09-17** `make verify` koşusunun kaydının olduğu gibi
> korunduğu bir fotoğraftır. O tarihten beri ağaç büyüdü ve aynı metrikler
> **2026-10-16 / 2026-10-17'de yeniden ölçüldü**; geçerli olan rakamlar
> README → "Running Tests" tablosundakilerdir. Satırları bugünkü durum sanmayın;
> güncel karşılıkları hemen aşağıdaki "2026-10-17'de yeniden ölçülen" satırıdır.

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

> **2026-10-17'de yeniden ölçülen (geçerli sayılar ve komutları):**
> toplanan Python testi **7447**
> (`./.venv/bin/python -m pytest --collect-only -q tests`, dosya-başına
> sayımların toplamı) · kapsama **%99.65 — 13 219 ifade / 46 eksik**
> (`./.venv/bin/python -m coverage json` + `totals` alanları; 2026-10-16
> `make verify` koşusunun `.coverage` veri dosyasından okundu) ·
> i18n paritesi **1345/1345**, anahtar kümeleri özdeş
> (`grep -cE '^[[:space:]]+"[^"]+": ' i18n/lang_tr.py i18n/lang_en.py`;
> dikkat: tam-4-boşluk grep `^    "` 1332 verir, 14 satır 2 boşlukla
> girintili) · masaüstü vitest **bildirimi 594** (55 izlenen test dosyası;
> `git ls-files -- desktop/src | grep -E '\.test\.tsx?$' | xargs grep -cE
> "^[[:space:]]*(it\|test)\(" | awk -F: '{s+=$2} END {print s}'`) ·
> Rust **8 passed / 0 failed** (`cd desktop/src-tauri && cargo test --release
> --offline`, 2026-10-17 bu makinede gerçekten koşuldu) · CI **19 job koşusu /
> 19 yeşil** `master` @ `4f25178` (`gh run view <run> --json jobs`).
> 7447 bir **toplama** sayıdır (7443 passed + 4 skipped): bu sayılar
> 2026-10-17 04:25'te bu makinede tam `make verify` koşusuyla elde edildi
> (RC=0, `--cov-fail-under=99` geçti), dolayısıyla "kaç test geçti" sorusunun
> cevabı **7443 passed + 4 skipped, 0 failed**'dir.

## Bilinen başarısızlık: yok — **2026-09-17 koşusunda** (2577 passed + 4 skipped, 0 failed)

> Bu başlık 2026-09-17 `make verify` koşusuna aittir ve o gün için
> doğrulanmıştır. 2026-10-16 koşusu da exit 0 / 0 failed raporlamıştır; ancak
> **bu belgeyi yazarken (2026-10-17) tam suit yeniden koşulmadı**, dolayısıyla
> "bilinen başarısızlık yok" cümlesi ancak sizin koşacağınız `make verify` ile
> bugünkü halini alır.

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
   derlendi (`pnpm tauri build --no-bundle`), o koşuda raporlanan 4 Rust testi
   + 591 vitest testi ve tam `make verify` geçtikten sonra kaynak ağacına
   yerleştirildi. *(Not — 2026-10-17 yeniden ölçümü: bugün ağaçta
   `grep -rn "#\[test\]" desktop/src-tauri/src` = **7** fonksiyon var ve
   `cargo test --release --offline` **7 passed / 0 failed** veriyor; yani o
   koşunun "4" sayısı ya sonradan eklenen 3 testten önceye ait ya da
   eksik raporlanmıştı — 4/4 hükmü bugün yeniden üretilemiyor. Benzer
   şekilde "591" yerine bugünkü izlenen vitest bildirimi **592**'dir;
   bu ikisi 2026-10-16 koşusunun kaydıdır, bugünkü kapı sayıları README
   "Running Tests" tablosundadır.)*
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

## 2026-10-17 03:41 (gece) — sidecar stdio çerçevelemesi: ikinci istek kayboluyordu

**Ölçülen.** `queue.add` ve `queue.start` aynı pipe paketine düştüğünde ikinci
isteğin yanıtı **hiç gelmiyordu**; yanıt, istemcinin üçüncü bir satır yazdığı
anda çıkıyordu. İki ayrı koşuda gecikme, ölçümün bitiş eşiğiyle birebir geldi:
200.0 sn ve 420.1 sn (`/tmp/pf_ev/trace.out`, `/tmp/pf_ev/trace2.out` —
`python3 /tmp/pf_ev/trace.py <paket>`, yalıtılmış `HOME` + gerçek `main.py serve`).
Kuyruğun ilk öğesi de o anda başlıyordu, yani dönüşüm değil **çağrının kendisi**
takılıyordu.

**Kök neden.** `serve()` fd'yi `select()` ile izleyip `sys.stdin.readline()` ile
okuyordu. `readline()` tek okumada birden fazla satır alırsa sonraki satırlar
`TextIOWrapper` tamponunda kalır; fd boşaldığı için `select()` onu bir daha
"hazır" görmez — satır, yeni bir girdi gelene kadar dispatch edilmez.

**Kullanıcıya etkisi.** Arka arkaya iki RPC çağrısı (toplu kuyruğu başlatmak,
hızlı tıklamalar, tek-örnek devrinin `queue.add`'i) süresiz bekler; arayüzde
spinner döner, kuyruk başlamaz, hata da görünmez. Sessiz takılma sınıfı.

**Düzeltme.** `core/api/protocol.py` artık çerçevelemeyi kendi tamponuyla yapıyor
(`_make_reader` fd→chunk, `_pump_stdin` chunk→satır); çerçevesiz baytlar 8 MB'ı
aşarsa `-32700` ile reddedilip tampon sıfırlanıyor. Eski sahte-`sys.stdin`
`select` testleri aynı dala (`_pump_stdin`) taşındı.

**Kanıt (kırmızı → yeşil).** Yeni `tests/test_stdio_frame_batched_lines.py`
(3 test, **gerçek alt süreç + gerçek boru**): düzeltme öncesi
`1,2,3 beklenirken gelen [1]` ve `1,2 beklenirken gelen [1]` (REAL_RC=1);
düzeltme sonrası üç test de geçti (REAL_RC=0). Birim testleri tek chunk→3 istek,
parçalı satır, EOF ve üst-sınır dallarını da kapsıyor.
Gerçek uygulama doğrulaması: aynı ölçüm düzeni düzeltme sonrası `queue.start`
yanıtını **0.1 sn**, ilk olayı 0.2 sn ve tam dönüşümü 6.4 sn'de verdi
(`/tmp/pf_ev/trace3.out`).

### Ölçülmemiş iddiam geri alındı: "iki dosyadan only ikincisi dönüştü"

Önceki oturumda «GUI'ye iki `--file` verildiğinde yalnızca `iki.deb` dönüştü»
yazıldı. Bu **okuma yanlışıydı** (Türkçe log satırlarının grep'le eksik
sayılması — bkz. `docs/DEAD_CODE_AUDIT.md` içindeki `LC_ALL=C` notu). Gerçek
sidecar + gerçek boru hattı ölçümünde iki paket de sırayla dönüştü:
`bir.deb` → kapı → `iki.deb` → kapı (`/tmp/pf_ev/harness.out`, `=== SONUC ===`
bloğu). Webview kuyruk mantığı ayrıca vitest ile kanıtlandı: 3 dosya → 3 sıralı
`pipeline.start`, başarısızlıktan sonra kuyruk devam ediyor
(`desktop/src/pages/__tests__/ConvertMultiFileQueue.test.tsx`).
Kalıcı doğrulama: kabuk tarafında çok-dosyalı argv **sıra** testi yoktu;
`desktop/src-tauri/src/lib.rs` içine üç-dosyalı sıra/tekillik testi eklendi.

Tasarım gerçeği (hata değil, not): uyumluluk kapısı kullanıcı kararını bekler ve
`event/finished` yalnız onay/red sonrası yayınlanır — yani kuyrukta ikinci dosya,
birincisinin diyaloğu kapanana kadar başlamaz.

### KAPATILDI 2026-10-17 08:16 — bulgu 1 ve bulgu 2 düzeltildi

**Bulgu 1 (düzeltildi):** `core/pipeline.py` artık dönüşüm başarılı olunca
`_preserve_converted_pkg` bayrağını kuruyor; `_cleanup()` paketi geçici dizinden
girdinin yanına (`_result.original_file.parent`, `cli.py:158` kuralı) taşıyor.
Mevcut dosya **asla ezilmiyor** (`demo.pkg.tar.zst.2` şeklinde sayısal sonek —
`Path.stem` çoklu uzantılarda parçaladığı için sonek tam adın sonunda).
Hedef dizin yazılamazsa gecici dizin **silinmiyor** (bayrak: `_preserve_failed`):
temizlik yerine paketin ayakta kalması tercih edildi; kullanıcı bir uyarı
loguyla bilgilendiriliyor. Normal kurulum yolu ve "paket zaten dışarıda" durumu
etkilenmiyor (`_is_path_in_dir` kontrolü).

**Bulgu 2 (düzeltildi):** kullanıcı kurulumu reddettiğinde INSTALL adımı artık
`skipped` etiketleniyor (`pipeline.label_atlandi`, iki dilde eklendi) ve
`error`/`label_basarisiz` çıktısı artık yazılmıyor. İptal (`cancel`) hâlâ
`error` — sessizce karışmadı. `success` semantiği bilerek değiştirilmedi:
pipeline kullanıcının istediği kurulumu yapamadığı için `False` kalıyor (söz
leşme değişikliği ayrı bir karar; webview zaten `skipped` durumuda StepIndicator
gösteriyor).

Kırmızı→yeşil kanıtı: `tests/test_pipeline_keep_pkg.py` (12 test) düzeltmeden
önce 11/11 kirmiziydi (gist: `git stash` + koşu), şimdi 12/12 yeşil;
`tests/test_pipeline_gate.py` (önceki davranışlar) değişmedi, hepsi yeşil.

Kapılar: `make verify` RC=0 (2026-10-17 08:16, %99.59 kapsama), ruff temiz,
mypy --strict temiz, `npx zeron scan .` 129/129 sağlıklı buton.

## Kalan insan adımları (ölçülmüş durum, 2026-10-16 gecesi)

1. **Yeni etiket gerekir — v2.2.0 bugünkü düzeltmeleri İÇERMİYOR.**
   `v2.2.0` tarball'ının sha256'sı 2026-10-16 gecesi yeniden indirilip
   doğrulandı; **2026-10-17'de bu oturumda da bağımsız olarak yeniden
   ölçüldü**: `1b4639c8baef8277afcde345154fb8c1e6ed42d2a6e15df11b59deb6d3aaec8b`,
   4 174 629 bayt — root `PKGBUILD` iddiası DOĞRU. Yeniden ölçme komutu:
   `curl -sL https://github.com/goun7/pkgforge/archive/refs/tags/v2.2.0.tar.gz -o /tmp/v220.tar.gz && sha256sum /tmp/v220.tar.gz && wc -c /tmp/v220.tar.gz`
   ("doğrulandı" kelimesi budur: tarball yeniden indirilip kök PKGBUILD'deki
   `sha256sums` ile karşılaştırıldı; başka bir trust-anchor iddiası içermez).
   Ama tarball 17 Eyl kodudur: modern UI yönlendirmesi, argv aktarımı,
   Qt parent düzeltmesi, kuyruk kalıcılığı ve Tauri 2.12 bu etikette yok.
   `git log v2.2.0..HEAD --oneline | wc -l` = **58** commit fark var. Yani
   stable `pkgforge` AUR paketi bugün kurulsa bayat GUI davranışını taşır.
   Çözüm: `v2.2.1` etiketi + root PKGBUILD'de `pkgver/sha256sums` yenilemesi
   (geri döndürülemez/ethkî adım olduğu için kullanıcı onayı beklenir).
2. AUR gönderimi: `pkgforge-git` PKGBUILD'i 2026-10-16'da **gerçekten
   derlendi** — `makepkg -f --noconfirm --skipinteg`, exit 0 → 18,9 MB paket;
   `usr/lib/pkgforge/desktop/{pkgforge-desktop, pkgforge-sidecar}` pakette.
   **Okur için kritik koşullu not:** `--skipinteg` bütünlük
   kontrollerini (sum doğrulama + source/doğrulama adımları) **atlar**. Yani
   bu derleme "source'ları doğrulanmış bir AUR derlemesi" **değildir**;
   `pkgforge-git` `source = git+https://…` kullandığı için `sha256sums = SKIP`
   zaten standarttır (`packaging/aur/pkgforge-git/.SRCINFO`), ama bu koşumda
   alınan exit 0 yalnızca "derleme tamamlandı" demektir; "girdiler doğrulandı"
   demek **değildir**. Bütünlük kapısını gerçekten görmek için `makepkg -f
   --noconfirm` (`--skipinteg` **sansız**) koşulmalıdır.
   `namcap`: **0 hata, 471 uyarı** — uyarıların 454'ü namcap'ın kendi
   modüllerimizi ("core.*", "ui.*") dış bağımlı sanması, kalanı tipik
   sezgisel notlar. Bu sayımlar 2026-10-16 derleme çıktısından alındı;
   2026-10-17'de yeniden üretilmedi (tam AUR derlemesi + ağ ister).
   Yeniden ölçmek için:
   `namcap pkgforge-git-*.pkg.tar.zst > /tmp/namcap.log; grep -cE '^E: ' /tmp/namcap.log; grep -cE '^W: ' /tmp/namcap.log`.
   **Koşul:** `namcap` kök ve `pkgforge-git` PKGBUILD'lerinde `depends` değil
   **`optdepends`** satırıdır (`grep -n "optdepends" -A12 PKGBUILD`); kurulu
   olmadığı sistemlerde dönüşüm raporu "namcap bulunamadı, statik analiz
   atlandı" der (`core/compatibility_checker.py::_run_namcap`). Aynı şekilde
   `clamav` de `optdepends`'tır ve bu makinede `clamscan` kurulu **değil**
   (`which namcap clamscan`), dolayısıyla ClamAV katmanı varsayılan olarak
   çalışmıyor. Temiz chroot koşumu (`extra-xdg-build`) ayrıca denenmedi;
   sudo/chroot ister.
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
