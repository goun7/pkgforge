# Otonom Tur Raporu — 2026-10-17

`date`: Cts 17 Eki 2026 16:50:28 +03 (tur kapanış ölçümü)
Kapsam: 12 saatlik kesintisiz otonom tur, 5 madde. **5/5 tamamlandı.**

## 1. Kapanış özeti

Goal kapsamının beş maddesinin de kapandığını, her iddinin çalıştırılmış komut
çıktısıyla desteklendiğini bildirir. Hiçbir değişiklik push edilmedi, PR
birleştirilmedi, etiket vurulmadı, AUR'a dokunulmadı. Tüm commit'ler lokal.

Çalışma ağacı: `git status --short` → **0 satır (temiz)**.
Tur commit'leri: `git log --oneline 4f25178..HEAD` → **10 commit**,
`git diff --stat 4f25178..HEAD` → **46 dosya, +2570 / −300**.

```
722e7b6 test(webview-acl): event/* webview ulaşımının önkoşullarını regression testine kilitle
e42b814 docs(webview-olaylari): Rust→JS event/* yayininin webview'e ulastigini uçtan uca kanıtla
ae838ee fix(queue): toplu kuyruk da kayitli output_dir ayarini artik okuyor
24fd529 test(api): RPC param sozlesme kilidi; olu settings output_dir artık kullaniliyor
041e503 fix(api): pipeline.start artik install/out_dir parametrelerine saygi gosteriyor
0ffc93b fix(i18n): dead queue.* anahtarlari silindi; dead-key kilicindaki f-string koruma acigi kapatildi
89ef2ce test(isolation): testler artik makine durumuna degmeden tekrar uretilebilir
440e0b1 fix(pipeline): kurulum yapilmayan yollarda uretilen paket artık silinmiyor; reddi "basarisiz" etiketiyle gosterilmiyor
130ddcd fix(api,desktop): sidecar stdio cercevelemesi ikinci istegi yutuyordu; doküman sayilari yeniden olculdu
```

(Her commit `[Autonomous-2026-10-17]` imzasını ve geçerli bir PoE seal'ini taşır.)

## 2. Ürün düzeltmeleri (kullanıcıya görünen)

| # | Hata | Kanıt |
|---|------|-------|
| 130ddcd | Sidecar'ın stdio çerçevelemesi art arda ikinci RPC isteğini yutuyordu — arayüzde "bekliyor" takılı kalma | Çift-istek RPC testi; ikinci yanıt artık geliyor |
| 440e0b1 | `install: false` yollarında üretilen paket dönüşüm bitince **siliniyordu**; kullanıcı reddi "başarısız" etiketiyle görüyordu | Gerçek .deb üzerinde dönüşüm + paket diskte kaldı, kayıt doğru etiketle |
| 041e503 | `pipeline.start` RPC'si `install` ve `out_dir` parametrelerini sessizce **görmezden geliyordu** | Param sözleşme testi (24fd529) ile kilitlendi |
| ae838ee | Toplu kuyruk, ayarlarda kayıtlı `output_dir`'i okumuyordu | Kuyruk kaydı hedef dizine gidiyor |
| 0ffc93b | Ölü `queue.*` i18n anahtarları + dead-key kilidinde bir f-string enjeksiyon yüzeyi | anahtar taraması = 0; koruma testi |
| 89ef2ce | Testler gerçek `$HOME`/makine durumuna bağımlıydı (tekrar üretilemiyordu) | test HOME'u tmp'ye izole eden harness |

## 3. Kararıcı bulgu: Rust→JS olayları (madde 5)

**10-16'daki "Rust→JS özel olayları webview'a ulaşmıyor" iddiası ÇÜRÜTÜLDÜ — ürün
hatası değildi, ölçüm düzenekleri (test rig) kusurluydu.**

Kök neden, birbirinden bağımsız **iki önkoşulun** 10-16'daki proof-app'te
eksik olmasıydı (tauri-2.12.0 kaynağından okunup ölçüldü):

1. `window.__TAURI__` globali **ancak** `tauri.conf.json` → `app.withGlobalTauri:
   true` iken enjekte edilir. Üretim uygulaması bunu kullanmaz (yerine
   `@tauri-apps/api` modül import'u — bu doğru olan).
2. `listen()` bir RPC komutudur (`invoke("plugin:event|listen")`) ve `core:event`
   ACL izni gerektirir. Olmayınca promise **reddedilir**.

**Ölçümler** (`/tmp/pf_wvproov/run*.log`, repo dışı scratch):

- run3.log (capabilities olmadan): `WV| JS: listen(0) REDDEDILDI: Command
  plugin:event|listen not allowed by ACL` — reddin tam metni.
- run4.log (her iki önkoşul sağlanınca), **89 Rust `EMIT|`** → **96 webview `WV|`**
  rapor satırı, türlerine göre: `log: 62, progress: 14, step: 11, event/finished: 1`.
  Dönüşüm gerçek .deb üzerinde koştu, gerçek çıktı paketi üretildi.

Üretim zincirinin zaten doğru olduğu kanıtlandı:
`desktop/src-tauri/capabilities/default.json` → `core:default` →
`gen/schemas/acl-manifests.json` içinde `core:event:default` → `allow-listen` /
`allow-unlisten`. **Yani 10-16'da "kabuk bozuk" sonucu yanlıştı; ürün değişmedi.**

Düzeltmeler (commit e42b814): `docs/DEAD_CODE_AUDIT.md` "Bilinmeyen" bölümü
"ÇÖZÜLDÜ" olarak yeniden yazıldı; `docs/ROADMAP.md` F5.23 ve
`RELEASE_READINESS.md` aynı şekilde; `sidecar.rs` ve `lib.rs` docstring'leri
kuyruk-RPC tasarım kararını koruyarak 10-16 gözleminin test rig kökenini
açıklar. Tek-örnek devrinin RPC üzerinden yapılması kararının kendisi değişmedi
(aynı belgede nedeni yazılı).

Regression kilidi (commit 722e7b6): `tests/test_desktop_acl_webview.py` — 4 test.
Capability'den `core:default`'u geçici olarak çıkarıp rc=1 olduğunu ölçtüğümüz
negatif kontrolle doğrulandı, sonra geri kondu.

## 4. Ölü yüzey ve doküman denetimi (madde 3 + 4)

- RPC metotları (`core/api/registry.py` METHODS): 90 metot, **0 ölü**.
- i18n: ürün tarafında kullanılmayan `queue.*` anahtarları silindi (0ffc93b);
  katalog artık kullanılan anahtarlarla uyumlu.
- Doküman-iddiası vs gerçek: README sayıları ve ROADMAP faz satırları
  yeniden ölçülüp düzeltildi (130ddcd); var olan tek "AÇIK" işareti geçmiş
  zamanlı, çözülmüş bir cümlenin içinde (docs/DEAD_CODE_AUDIT.md:147).

## 5. Kapılar (her iş biriminin kapanışında)

- `make verify` → **RC=0**, coverage **%99.56** (pytest + ruff + mypy --strict +
  bandit -ll).
- `cargo check` + `cargo test` (desktop/src-tauri) → temiz.
- Frontend kapıları `/tmp/pf_fe_u7` kopyasında (bu makinada pnpm,
  kullanıcı seviyesindeki ~/pnpm-workspace.yaml yüzünden proje içinden çalışmaz): `pnpm install
  --frozen-lockfile`, `tsc -b`, `vite build`, `vitest run` → **rc=0**.
- `npx zeron scan .` → PASS (her ağaç ayrı; `npx zeron audit .` `.venv`
  gürültüsü için kullanılmadı).
- PoE seal'leri commit'lerde gömülü, örn. son ikisi:
  `[PoE rc=0 out=4cd7d73eff51004e diff=76c698556d38c1d3 time=2026-10-17T13:28:24.161Z]`
  (e42b814) ve
  `[PoE rc=0 out=4e808bb852ddad03 diff=5eb8e6a2be84fe4d time=2026-10-17T13:43:40.551Z]`
  (722e7b6).

Güvenlik: testler ocası makine durumuna dokunmaz (HOME tmp), production
secrets'e erişilmedi, hiçbir dosya kalıcı silinmedi.

## 6. Onay kuyruğu (senin kararın bekliyor)

Hiçbiri yapılmadı, hepsi geri-alması zor adımlar olduğu için sormadan bekletildi:

1. **v2.2.1 etiketi + AUR `pkgforge` (root) PKGBUILD'inde pkgver/sha256sums
   tazelemesi** — bu turdaki düzeltmeler release'e girmemiş durumda; etiket
   vurulursa AUR paketinin ellerle güncellenmesi gerekir.
2. **Push + PR birleştirme** — 10 lokal commit pushing hazır değil, onayın
   gerekli.
3. **AUR yayını** — dokunulmadı.

Scratch (repo dışı, istersen silebilirsin): `/tmp/pf_wvproov` (proof-app +
run1–4.log), `/tmp/pf_fe_u7` (frontend kapı kopyası).

## 7. Önerilen sıradaki (onayına bağlı)

- release notları v2.2.1 için hazırlanabilir (CHANGELOG'ta şekli var).
- Madde 1–4'ün tarama çıktıları `docs/` içinde kanıt olarak duruyor, tekrar
  koşulabilir: `make verify`, `tests/test_desktop_acl_webview.py::` 4 test.
