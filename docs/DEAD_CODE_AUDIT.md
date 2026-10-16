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
| TR/EN i18n anahtarı | 1417 | **72** | silindi → 1345 |
| Masaüstü `i18n.ts` anahtarı | 616 | **8** | silindi → 608 |
| İzlenen dosya | 1690+ | **69** | silindi (1,09 MB) |

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

## Bilinmeyen (kanıtsız bırakılmadı, kökü bulunamadı)

**Rust→JS özel olayları bu derlemede webview'a ulaşmıyor.** Ölçüm: olay adı
`pkgforge://open-files` ve `app/open-files` ile denendi; `emit` her iki
yönden (plugin soket thread'i + `run_on_main_thread` ile ana thread) `Ok`
döndü; yol politikası aynı path için `izinli` dedi; izolasyon denemesinde
(Zamanlayıcı→`emit`→JS dinleyici→`queue.add` RPC) `queue.db`'de satır
oluşmadı. Yani "gönderildi ama işlenmedi" hali belgeli.

Yanlız bu olaya mı özgün, yoksa sidecar'ın `event/log`, `event/finished`
itmeleri de mi ulaşmıyor — **bilinmiyor**, çünkü bunu uçtan uça doğrulayan tek
bir test yok: vitest'te `listen` mock'lu, `visual-qa` ise Tauri köprüsü olmayan
tarayıcıda koşuyor. Bu yüzden "canlı güncellemeler çalışıyor" da doğrulanmış
bir önerme değil; yanlız UI'nin donduğuna dair kullanıcı şikâyeti yok.

Çözüm için gereken: debug derlemesi + `WEBKIT_INSPECTOR_SERVER` ile WebKit
inspector'da `listen()` promise'inin akıbetine bakmak (reddediliyor mu,
çözümleniyor ama olay mı gelmiyor). Kuyruk devri bu belirsizliğe bağlı
kalmaması için zaten RPC üzerinden yapılıyor.

## Yeniden koşum

```bash
make verify                        # ruff + mypy --strict + bandit + pytest (%99 kapı)
cd desktop && pnpm tauri build --no-bundle   # ikili: src-tauri/target/release/pkgforge-desktop
sudo ./scripts/install.sh          # kurulum; ikili varsa modern arayüzü de kopyalar
```

Not: bu makinede `pnpm` kullanıcı seviyesindeki `~/pnpm-workspace.yaml`
yüzünden proje içinden çalışmıyor; frontend/Rust kapıları kopyada koşuluyor
(`cp -r desktop /tmp/pf_ta && cd /tmp/pf_ta && pnpm install --frozen-lockfile`).
