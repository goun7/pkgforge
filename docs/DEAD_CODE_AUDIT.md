# Atıl Dosya ve Ölü Metin Denetimi (2026-10-16)

Kullanıcı isteği: "projenin içinde atıl kalmış her türlü kullanmadığımız
dosyayı da tespit etmeliyiz." Bu belge tespit yöntemi, ölçülen sonuçlar,
silinenler ve **bilerek silinmeyenler** kaydıdır.

## Yöntem (dört eksende, salt-okunur)

1. **Modül grafı:** `git ls-files` altındaki her `core/*.py` ve `ui/*.py`
   modülü için üç import biçimi arandı (`core.x`, `from core import x`,
   `import x`). Testler, CI, `tools/`, `scripts/`, `desktop/` dahil tüm kaynak
   tarandı.
2. **i18n anahtarları:** katalog anahtarı ↔ çağrı noktası. Çağrı noktası
   sayılırken yalnızca `tr("...")` literalsi değil, AST'deki **tüm** string
   sabitleri (ternary dalları, sabit anahtar listeleri), f-string önekleri
   (`tr(f"month.{mm}")` → `month.` ailesi canlı) ve masaüstü `.ts/.tsx`
   içindeki tırnaklı anahtarlar (`labelKey: "navConvert"`) alındı.
3. **Dosya referansları:** her izlenen dosyanın adı ve gövdesi (uzantısız)
   tüm metin kaynaklarında arandı; asset ve ikon sınıflarında `tauri.conf.json`,
   `install.sh`, `.desktop`, `pyproject.toml` referansları ayrıca kontrol edildi.
4. **Derleme artefaktları:** izlenen dosyalarda ELF/gzip başlığı, `*.pyc`,
   `.MTREE`, `.BUILDINFO`, `*.tsbuildinfo` ve >400 KB dosyalar listelendi.

## Ölçülen sonuç

| Eksen | Taranan | Ölü bulunan | İşlem |
|---|---|---|---|
| Python modülü (`core/`, `ui/`) | 111 | 0 (yalnızca 7 `__init__.py`) | gerek yok |
| TR/EN i18n anahtarı (dil başına) | 1417 → **1416 yeniden ölçüldü** | **72** (doğrulandı) | silindi → 1345 · bugün **1345** |
| Masaüstü `i18n.ts` anahtarı (dil başına) | 616 (doğrulandı) | **8** (doğrulandı) | silindi → 608 · bugün de **608** |
| İzlenen dosya | 1690+ → **829 yeniden ölçüldü** | **69** (65 net düşüş ölçüldü) | silindi (1,09 MB) |

> **Bu satırlar 2026-10-16 denetim kaydının fotoğrafıdır; 2026-10-17'de
> ağaçtan yeniden üretildi.** Komutlar ve sonuçlar:
>
> - Silme commit'i: `0d50ed2` ("fix(main,desktop): modern arayuz her giris
>   noktasindan aciliyor…"). Öncesi/sonrası anahtar kümeleri AST ile sayıldı:
>   `i18n/lang_tr.py` → `0d50ed2^` = **1416** tekil anahtar, `0d50ed2` = **1345**
>   → o commit **72 ölü anahtarı sildi ve 1 anahtar ekledi**
>   (1416 − 72 + 1 = 1345). Yani "72 silindi" satırı **birebir doğru**;
>   "1417 taranan" ise ağaçtan üretilemiyor — yeniden ölçülen taranan sayı
>   **1416**'dır. Bugünkü sayı **1345** (2026-10-17'de `api.istem_satiri_cok_uzun` eklendi): `327a077` sonrasında 1 anahtar ekledi.
> - Bugünkü Python anahtar sayısı:
>   `LC_ALL=C grep -cE '^[[:space:]]+"[^"]+": ' i18n/lang_tr.py i18n/lang_en.py` → **1345 / 1345**.
>   Dikkat: tam-4-boşluk deseni (`'^    "[^"]+": '`) **1332** verir — 14 satır
>   2 boşlukla girintili; bu sayı anahtar sayısı değil, satır sayımıdır.
> - Masaüstü: `LC_ALL=C grep -cE '^    [A-Za-z_][A-Za-z0-9_]*: ' desktop/src/lib/i18n.ts`
>   → **1216**, yani **608 tr + 608 en** (`0d50ed2^` aynı sayımla **616 + 616**;
>   8 anahtar silindi → 608, bugün hâlâ 608). **Bu satır bir tuzağa işaret
>   ediyor:** yerel ayar `tr_TR.UTF-8` iken aynı desen **532** veriyor (GNU grep
>   aralık sınıfları yerelden etkileniyor). Sayımları **mutlaka `LC_ALL=C`** ile
>   koşun; bu belgedeki 616/608 sayıları `LC_ALL=C` ile yeniden üretilebilir.
> - İzlenen dosya: `git ls-tree -r --name-only 0d50ed2^ | wc -l` → **829**,
>   `0d50ed2` → **764**, `HEAD` → **765**. Tablodaki "1690+" izlenen-dosya
>   sayımından değil, denetimin kullandığı daha geniş tarama evreninden
>   (tüm çalışma ağacı) geliyor; bu yüzden bu sütun **yeniden üretilemez** ve
>   ölü-bulunan/silinen sayıları tek başına referans alınmamalıdır.
> - Python modülü: `git ls-tree -r --name-only HEAD | grep -cE '^(core|ui)/[^/]+\.py$'`
>   → **89** (0d50ed2^'da da 89). Tablodaki "111" alt paketler/giriş noktaları
>   ile birlikte yapılmış bir sayımdır; dar tanımla yeniden üretilemez.

Silinen 72 Python anahtarının hiçbirinin **prodüksiyon kodunda, testlerde,
belgelerde veya masaüstü tarafında** tek bir referansı yoktu (sınıflandırma
çıktısı: 72 "hiç referans yok", 0 "yalnız testte", 0 "yalnız belgede").

## Silinen 69 dosya

| Kategori | Adet | Neden güvenli |
|---|---|---|
| `desktop/src-tauri/icons/{Square*.png, StoreLogo.png, android/**, ios/**, app-icon.png}` | 60 | `tauri.conf.json` → `bundle.targets = ["deb"]`, `bundle.icon` listesi yalnızca `32x32/128x128/128x128@2x/icon.icns/icon.ico` istiyor. Windows/macOS/mobile ikonları hiçbir yerde geçmiyor; `pnpm tauri icon` ile yeniden üretilir. |
| `utest/lictest/pkg/**`, `utest/out/**` | 11 | `makepkg` kurgulama/çıktı dizinleri (`.BUILDINFO`, `.MTREE`, `.PKGINFO`, sıkıştırılmış `.pkg.tar.zst`). CI ve testler yalnızca `utest/hello_1.0.0-1_amd64.deb`, `utest/fixtures/*.rpm`, `utest/lictest/lictest-1.0.0-1-any.pkg.tar.zst` dosyalarını okuyor; bu üçü **duruyor**. |
| `utest/shots/*.png`, `utest/widget_tree.txt` | 6 | `utest/gui_screens.py` / `gui_audit.py` çıktısı; kaynak betikler duruyor, çıktı yeniden üretilir. `.gitignore` zaten `utest/*` kuralıyla bunları engelliyor. |
| `scripts/install_desktop.sh`, `scripts/pkgforge-desktop.sh`, `tools/check_tr_identity.py` | 3 | Ilki `install.sh` + `uninstall.sh` tarafından tam olarak yapılıyor (menü girişi + SVG + MIME). Ikincisi `main.py::_launch_desktop` ile birebir aynı ortam değişkenlerini ayarlıyor ve `pkgforge desktop` onu çağırıyor; wheel `data-files` listesinde de yok. Ucuncu tek seferlik yerelleştirme göç kanıtıydı; kalıcı gözcüler `tests/test_i18n_output_leaks.py` ve `tests/test_i18n_key_drift.py` sınıfı kapatıyor. |

## Bilerek silinmeyenler

- **`assets/logo/**` (31 dosya, 376 KB):** marka kaynak görselleri (16→1024 px,
  `.iconset`, `.ico`, SVG'ler). Uygulama ikonu `data/pkgforge.svg`'dan geliyor;
  bu dosyalara kod/CI referansı yok. Silmek ikon üretim kabiliyetini kaybeder —
  "ölü" değil, kaynak.
- **`docs/design/**` (1,3 MB, logo konseptleri + UI mockup'ları):** tasarım
  geçmişi. Yeniden üretilemez (tasarım kararlarının kanıtı), bu yüzden duruyor.
- **`utest/*.py` (4 dosya):** silinen çıktıları üreten gerçek-araç probe
  betikleri (`gui_screens.py`, `gui_audit.py`, `inspect_report.py`,
  `e2e_decision_gate.py`). Kaynak, artıktan değerlidir.
- **`core/http_assets/dist/swagger-ui-bundle.js` (1,5 MB):** `core/api/http.py`
  tarafından sunuluyor → canlı.

## Denetim sırasında bulunan üç gerçek hata

1. **AppImage menü girişi hiçbir şey açmıyordu:** `packaging/appimage/pkgforge.desktop`
   `Exec=pkgforge` kullanıyordu; alt komutsuz `pkgforge` yardım basıp çıkıyor ve
   `Terminal=false` olduğu için kullanıcı hiçbir şey görmüyordu. `Exec=pkgforge
   desktop %f` + `MimeType=` yapıldı (`data/pkgforge.desktop` ile hizalandı).
2. **Modern arayüz açılıp dosyayı görmezden geliyordu:** Rust kabuğu argv'yi
   okumuyor, frontend de sormuyordu → "Birlikte aç" boş pencere açıyordu.
   Kabuk artık `initial_files` komutuyla var olan dosyaların mutlak yollarını
   veriyor, Convert sayfası açılışta kuyruğa alıyor. Kanıt: izole HOME'da
   `pkgforge --file …/gelip.deb` → `Pipeline başlatıldı: gelip.deb`,
   `✓ Dönüşüm tamamlandı`, ardından onay kapısı.
3. **Her masaüstü dönüştürmesinde Qt hatası:** `Converter(self._tools, self)`
   sidecar'ın worker thread'inde Qt parent'i reddediyordu (`Cannot create
   children for a parent that is in a different thread`). `_qt_parent()` artık
   thread farklıysa `None` döndürüyor; nesne ömrü Python alanlarında tutulan
   referanslarla garanti altında. Gerçek çalıştırma sonrası hata sayısı 0.

## Kalıcı kilitler

- `tests/test_pipeline_qt_parent.py` — davranış + AST anahtarı:
  `Converter(..., self)` deseni geri gelirse test FAIL verir (kırmızı kanıtı
  üretildi: satır 1057 geri alınca test FAIL verdi).
- `tests/test_i18n_no_dead_keys.py` — TR, EN ve TS kataloglarında çağrı noktası
  olmayan anahtar kümesini boşta tutar (geçici ölü anahtar eklenerek FAIL
  edildiği doğrulandı).
- `desktop/src/pages/__tests__/ConvertArgvFiles.test.tsx` — kabuktan gelen
  dosyanın kuyruğa girdiğini, komut yoksa/bozuk şekilli yanıt geldiğinde sessiz
  kaldığını kanıtlar (etki kaldırılınca 3/3 FAIL).

## İzlenmeyen ama diskte duran bayat artefaktlar (ikinci geçiş)

İlk geçiş `git ls-files` üzerinden yapıldığı için **ignore edilmiş** derleme
çıktıları görülmüyordu. Disk taramasında ölçülen:

| Yol | Boyut | Durum |
|---|---|---|
| `build/` (PyInstaller `sidecar/` + `pkgforge-sidecar.spec`) | 111 MB | 17 Eyl snapshot'un derleme artığı; `bash desktop/scripts/build-sidecar.sh` ile yeniden üretilir. Silinmedi (kullanıcı kararı), `rm -rf build` ile geri kazanılır. |
| `desktop/src-tauri/binaries/pkgforge-sidecar-x86_64-unknown-linux-gnu` | 97 MB | 17 Eyl tarihli gömülü Python motoru. Git'te izlenmiyor ama **install.sh bunu sisteme kopyalıyordu**. |
| `desktop/src-tauri/target/` | 6,2 MB | Bugünkü Tauri derlemesi (canlı; `_find_desktop_binary()` bunu buluyor). |

Tam da bu 97 MB'lik snapshot yüzünden gerçek bir hata çıktı: kurulumda GUI, yanına kopyalanan **bir aylık** motoru çalıştırıyorken CLI taze kodu
çalıştırıyordu (ölçüm: `/usr/lib/pkgforge/desktop/pkgforge-sidecar serve`
süreci, mtime 17 Eyl; Qt parent düzeltmesi 16 Ekim). Düzeltme iki parçalı:
`main.py::_launch_desktop` kabuk kurulum ağacının içindeyse artık
`PKGFORGE_SIDECAR=python` zorluyor, `install.sh` ise Python ağacından eski
snapshot'i kopyalamıyor ve daha önce kopyalanmış olanı kaldırıyor.
Kanıt: taklit `/usr/lib` düzeninde dönüşüm canlı ağaçtan koştu, gömülü sidecar'ın imzası log'da 0 kez göründü.

## Bilinmeyen → ÇÖZÜLDÜ (2026-10-17): Rust→JS olaylarının webview'e ulaşması

**10-16 bulgusu (önceki durum):** Rust→JS *özel* olayları bu derlemede
webview'a ulaşmıyordu. Ölçüm: olay adı `pkgforge://open-files` ve
`app/open-files` ile denendi; `emit` her iki yönden (plugin soket thread'i +
`run_on_main_thread` ile ana thread) `Ok` döndü; yol politikası aynı path için
`izinli` dedi; izolasyon denemesinde (Zamanlayıcı→`emit`→JS dinleyici→
`queue.add` RPC) `queue.db`'de satır oluşmadı. Yani "gönderildi ama
işlenmedi" hali belgeliydi. Sidecar'ın `event/log`, `event/finished`
itmelerinin ulaşıp ulaşmadığı bilinmiyordu (uçtan uca doğrulayan test yoktu:
vitest'te `listen` mock'lu, `visual-qa` Tauri köprüsü olmayan tarayıcıda
koşuyor).

**Kök neden (2026-10-17, kaynak-kodu okuma + canlı webview ile kanıtlandı):**
olayların webview'e ulaşması iki bağımsız koşula bağlıdır ve 10-16 ölçümünde
ikisi de eksikti:

1. **`window.__TAURI__` yalnızca `withGlobalTauri: true` durumunda vardır.**
   Tauri 2 global nesneyi yalnızca `app.withGlobalTauri` (tauri.conf.json)
   açıkken enjekte eder; üretim kabuğumuz bu alanı hiç kullanmamıştır
   (`desktop/src-tauri/tauri.conf.json`'da yok). Üretim JS'i modül import'uyla
   (`@tauri-apps/api`) çalıştığından bu bir hata değildir — ama 10-16'daki el
   denemesi global nesneyi kullandığı için JS tarafı sessizce ölmüştür.
2. **`plugin:event|listen` bir ACL yetkisi gerektirir.** `listen()` bir IPC
   komutudur: `invoke("plugin:event|listen", …)` → Rust `Webview::listen_js`
   → `listeners.listen_js`. Yetki kümesi yoksa promise **`Command
   plugin:event|listen not allowed by ACL`** ile reddedilir ve hiçbir olay
   gelmez (birebir ölçüldü, aşağıda). Üretim kabuğu `capabilities/default.json`
   listesinde `core:default` içerir → compiled ACL'de `core:event:default` →
   `allow-listen` + `allow-unlisten` + `allow-emit` + `allow-emit-to`
   (kanıt: `gen/schemas/acl-manifests.json`,
   `core:event.default_permission.permissions`). Yani üretim yapılandırması
   doğrudur; 10-16 deneyi bu koşulları sağlamıyordu.

Teslim mekanizması kaynak-kod düzeyinde de doğrulandı (tauri-2.12.0):
`app.emit(event, payload)` → `AppManager::emit` → `listeners.emit_js`
(`js_event_listeners` tablosundan webview label'i + olay adıyla eşleşen
handler id'leri) → `Webview::emit_js` → `eval(emit_js_script)` →
`window.__internal_unstable_listeners_function_id__(eventData, ids)` →
`__TAURI_INTERNALS__.runCallback(handlerId, eventData)`. Olay adında `/`
serbesttir (`event_name.rs`: alfanümerik + `-` `/` `:` `_`) — dolayısıyla
`event/finished` biçimi engel değildir.

**Uçtan uca kanıt (2026-10-17, gerçek derleme + gerçek WebKit2GTK webview +
gerçek Python sidecar):** minimal bir Tauri 2 kabuğu (`/tmp/pf_wvproov`,
depoda değil) üretim devresini birebir taklit eder: repo kökünden
`.venv/bin/python main.py serve` sidecar'ı, aynı `route_line` → `app.emit`
yönlendirmesi, `rpc_call` IPC komutu ve `capabilities/default.json` içinde
`core:default`. Webview JS'i her `listen()` çağrısını ve her olay alımını
`rapor_et` IPC'siyle stdout'a yazar. Ölçüm (`run4.log`, HOME=tmp izole):

- Rust tarafı 89 `emit` (62 `event/log`, 14 `event/progress`,
  11 `event/step_changed`, 1 `event/compatibility_ready`, 1 `event/finished`),
- webview **96 rapor satırı** aldı: `log` 62, `progress` 14, `step` 11,
  `finished` 1 — yani emit'lerin tamamı,
- `event/finished` payload: `success: true`, gerçek çıktı paketi
  `utest/hello-1.0.0-1-x86_64.pkg.tar.zst`,
- `listen()` promise'inin akıbeti de kayıt altına alındı: capabilities
  yokken `Command plugin:event|listen not allowed by ACL` (`run3.log`),
  `core:default` eklenince `listen(0) tamam, id alindi` (`run4.log`).

Sonuç: **sidecar'ın tüm `event/*` itmeleri webview'in JS dinleyicilerine
ulaşır.** 10-16 "ulaşmıyor" bulgusu deneme düzeneğinin (global nesne + ACL)
eksikliğinden kaynaklanıyordu, ürün kodunda veya kabuk kodunda bir hata
değildir; üretim `capabilities/default.json` zaten doğru yetki kümesini
içerir.

Geriye kalan tek boşluk: 10-16'daki *özel* `app/open-files` olayının
üretim derlemesiyle (globalTauri kapalı, ACL izinli) uçtan uca
ölçülmemiş olması. Mekanizma yukarıda çalıştığına göre bunun da çalışması
beklenir; yine de deney üretim kabuğu binary'siyle bir kez tekrar
edilmelidir.

## Yeniden koşum

## Üçüncü geçiş (2026-10-17): RPC / TS export / i18n ölü yüzey

Hedef: belirli yüzeylerde kalan ölü kod kalıntılarını ölçmek. Üç eksen
tamamlandı, hepsi AST/substring taramasıyla üretildi ve elle doğrulandı:

| Eksen | Ölçülen | Ölü | İşlem |
|---|---|---|---|
| RPC metotları (`core/api/registry.py` METHODS) | 90 | **0** | gerek yok |
| Masaüstü TS exportları (`desktop/src`) | 162 | **0** | gerek yok |
| TR/EN i18n anahtarı | 1350 | **5** (doğrulandı) | silindi → 1345 |

Silinen 5 anahtar (TR ve EN kataloglarının ikisinde de):

- `queue.item_status`, `queue.waiting`, `queue.converting`, `queue.done`,
  `queue.error` — hiçbir üretim dosyasında, testte, belgede veya masaüstü
  kataloğunda geçmiyor (`desktop/src/lib/i18n.ts`'te karşılığı yok).

Bu 5 anahtar önceki denetimde yakalanmadı çünkü **kilidin kendisinde bir
hataydı**: `tests/test_i18n_no_dead_keys.py` her f-string'in başını bir i18n
anahtar öneki sayıyordu. `core/api/handlers_queue.py:194`'teki
`item_id = f"q{_queue_seq}"` bir `tr()` çağrısı değil, ama `"q"` öneki bütün
`queue.*` ailesini canlı gibi gösteriyordu. Düzeltme: yalnızca bir `tr(...)`
çağrısının **içindeki** f-string'ler dinamik anahtar öneki sayılıyor
(`_tr_icinde_mi`). Kırmızı kanıt: `tr()` kapsama kontrolü kaldırılınca misma
tarama 5 anahtarı "canlı" gösteriyor (guard'ın eski davranışı tam olarak
üretildi). Aynı aile, doğru çalışan taraf için bir **yanlış-pozitif tuzağı**
da içeriyordu: `month.*` anahtarları gerçekten canlı
(`core/stats_wrapped.py:22` → `tr(f"month.{int(mm)}")`) — bunlar doğru
korundu.

Yeni kilitler (`tests/test_i18n_no_dead_keys.py`):

- `test_tr_disi_f_string_on_ek_i18n_canliligi_yanlis_eqlemesin` — `"q"`
  öneki toplanmamalı (guard tekrar bozulursa FAIL).
- `test_tr_icindeki_f_string_on_eki_canli_sayiliyor` — `"month."` öneki
  toplanmalı (gerçek dinamik aile).
- `test_queue_dead_anahtarlar_katalogdan_cikarildi` — silinen 5 anahtar
  geri dönerse FAIL.

Parite: TR/EN 1345/1345, anahtar kümeleri özdeş
(`tests/test_i18n_parity.py`).

## Yeniden koşum

```bash
make verify                        # ruff + mypy --strict + bandit + pytest (%99 kapı)
cd desktop && pnpm tauri build --no-bundle   # ikili: src-tauri/target/release/pkgforge-desktop
sudo ./scripts/install.sh          # kurulum; ikili varsa modern arayüzü de kopyalar
```

Not: bu makinede `pnpm` kullanıcı seviyesindeki `~/pnpm-workspace.yaml`
yüzünden proje içinden çalışmıyor; frontend/Rust kapıları kopyada koşuluyor
(`cp -r desktop /tmp/pf_ta && cd /tmp/pf_ta && pnpm install --frozen-lockfile`).
