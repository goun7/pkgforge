# Changelog

All notable changes to PkgForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

> Bu bölüm bir sonraki sürüm için boş tutulur.

### Fixed — 2026-10-18 otonom turu

- **Build-system algılayıcıları tekilleştirildi** (`core/aur_publish.py`):
  aynı repo için üç farklı çağırma yeri üç farklı sonuç veriyordu.
  `handle_source_generate` (from-source PKGBUILD sihirbazı) elle yazılmış
  bir if-else merdiveni kullanıyordu ve `pyproject.toml`-only bir repoyu
  `unknown` sanıyordu — sonuçta `python -m build` yerine derleme başarısız
  olan `gcc`+`make` PKGBUILD'i üretiliyordu. Artık tek marker tablosu
  (`_BUILD_SYSTEM_MARKERS`) üç yüzeyde de (intake, AUR hazırlama,
  from-source) paylaşılmaktadır; `configure.ac` ve `setup.cfg` de tanınır.
- **from-source node dalı ulaşılabilir hale getirildi** (`core/from_source.py`):
  hiçbir algılayıcı `node` döndürmediği için bu dal ölü kodd uygulanıyordu.
- **from-source'e `go` ve `autoreconf` yolları eklendi** (`core/from_source.py`):
  `go.mod` repoları `go build -trimpath` ile; `configure.ac`-only autotools
  repoları `autoreconf -fi` ile derlenir. `go.mod` içindeki açık `version`
  satırı `pkgver`'a yansır (öncesi: 0.0.1).
- Kanıt: `tests/test_build_system_unified.py` (24 test) — ürettilen
  PKGBUILD gerçek `makepkg` ile derlenip paket üretmektedir
  (namcap 0 hata). Tamirim öncesi kırmızı: 7 test fail.
- **HTTP panosunun form denetimlerine erişilebilir ad eklendi**
  (`core/http_assets/dashboard.html`): `zeron audit core` 2 adet P0
  (WCAG 4.1.2 ACCESSIBLE_NAME) veriyordu — `input#tok` ve `select#mth`
  adsızdı. Artık `<label>` + `aria-label` taşımaktalar; regression testi
  `tests/test_http_assets.py`'de.

## [2.2.2] - 2026-10-18

> **v2.2.0 sonrası 68 commit'in son 10'u (2026-10-17 otonom turu).**
> Sayım komutları: `git log v2.2.0..HEAD --oneline | wc -l` → **68**
> (`fix` 35 / `feat` 3 / `test` 14 / `docs` 8 / `chore` 8);
> `git log --since=2026-10-17 --oneline | wc -l` → **10**
> (`fix` 5 / `test` 3 / `docs` 2).
> Aşağıdaki "v2.2.0 sonrası" bölümü 55 commit'lik 2026-09-18 … 2026-10-16
> aralığını özetler ve burada tekrar edilmez.

### Fixed — 2026-10-17 otonom turu (5 commit)
- **api/desktop**: sidecar'ın stdio çerçevelemesi art arda ikinci RPC
  isteğini yutuyordu; artık her istek yanıtını veriyor
  (`130ddcd`).
- **pipeline**: `install: false` (yalnızca dönüşüm) yollarında üretilen
  paket dönüşüm bitince siliniyordu ve red "başarısız" etiketiyle
  gösteriliyordu; artık paket bırakılıyor ve red doğru etiketleniyor
  (`440e0b1`).
- **api**: `pipeline.start` RPC'si `install` ve `out_dir` parametrelerini
  sessizce görmezden geliyordu; artık saygı gösteriyor (`041e503`).
- **queue**: toplu kuyruk ayarlarda kayıtlı `output_dir`'i okumuyordu
  (`ae838ee`).
- **i18n**: kullanılmayan `queue.*` katalog anahtarları silindi;
  dead-key kilidinde f-string enjeksiyon yüzeyi kapatıldı (`0ffc93b`).

### Changed — 2026-10-17 otonom turu (test + docs, 5 commit)
- **test**: RPC param sözleşme kilidi; ölü `settings.output_dir` artık
  kullanılıyor (`24fd529`); testler artık gerçek `$HOME`'a dokunmadan
  tekrar üretilebilir (`89ef2ce`); `event/*` webview ulaşımının iki
  önkoşulu (`withGlobalTauri` globali + `core:event` ACL) regression
  testine kilitlendi (`722e7b6`).
- **docs**: Rust→JS `event/*` yayınının webview'e ulaştığı uçtan uca
  kanıtlandı (10-16'daki "ulaşmıyor" iddiası test-rig kusuru olarak
  çürütüldü; 89 emit → 96 webview rapor satırı) (`e42b814`, `722e7b6`);
  tur kapanış raporu `docs/OTONOM_TUR_RAPORU_2026-10-17.md`.

### Fixed — CI onarımı (v2.2.1 etiketi yayınsız kaldı, bu sürüme alındı)
- v2.2.1 etiketi CI'da kırmızı kalan bir commit'e atılmıştı; release
  workflow'unun gate'i testlerden önce hiç asset üretmedi durdu, dolayısıyla
  yayınlanmış v2.2.1 içeriği yok (runbook: tag taşınmaz → yeni patch).
- **ci**: sidecar testleri sabit `.venv/bin/python` ve `gen/schemas/
  acl-manifests.json` (tauri-build çıktısı) varsayiyordu; CI'da ikisi de
  yoktu. Yorumlayıcı artık `sys.executable`'a düşüyor, ACL testi çıktı
  yoksa atlıyor.
- **ci**: canlı RPC testleri CI (ubuntu) image'inde `makepkg` olmadığı için
  boş olay listesiyle patlıyordu; artık sistem aracı eksikse atlıyor
  (`PF_TEST_ARAC_EKSIK=1` ile koşul yeniden üretildi).

### Kapılar (2026-10-17 ölçümü)
- Python: **7494 test (7490 pass + 4 skip)** — ruff, mypy --strict, bandit
  -ll temiz; coverage **%99.56** (`make verify` RC=0).
- Rust (`desktop/src-tauri`): `cargo test` 8/8 pass, `cargo clippy` 0 warning.
- Frontend: `tsc -b` + `vite build` temiz, `vitest run` **594/594** (55 dosya).
- ZERON: `scan` 129 buton / 0 critical; `doctor` 23/23 PASS, health 100/100.
- Sürüm 5 yerde senkron (2.2.1) ve `tests/test_version_parity.py` ile
  kilitli; AppStream metainfo ve SBOM araç sürümü aynı kaynaktan gelir
  (önceki sabit değerler sürüm yükselince kıran testlere neden oluyordu).

### Önceki v2.2.0 sonrası değişiklikler (2026-09-18 … 2026-10-16, 58 commit)


> **Bu bölüm v2.2.0 etiketinden sonraki 2026-09-18 … 2026-10-16
> aralığını (58 commit) özetler.** Aşağıdaki üç grup 2026-10-01 … 2026-10-16 arasını özetler
> (55 commit); bu bloğun altındaki "gelir stratejisi sadeleştirme (2026-09-18)"
> bölümü zaten belgelenmiş 3 commit'i içerir, tekrar edilmedi.
> Sayım ve liste komutları (bu satırlar uydurma değildir, commit mesajlarından
> üretildi):
> `git log v2.2.0..HEAD --oneline | wc -l` → **58** ·
> `git log v2.2.0..HEAD --since=2026-10-01 --oneline | wc -l` → **55** ·
> grup listesi (2026-10-01 sonrası alt aralığı):
> `git log v2.2.0..HEAD --since=2026-10-01 --format=%s | grep -cE '^fix'` → **29** /
> `…'^feat'` → **3** / `…'^chore'` → **8** / `…'^test'` → **11** / `…'^docs'` → **4**
> (toplam 55). Tam aralıkta (`--since` sansız) fix **30**, docs **6** olur —
> 2026-09-18 tarihli 3 commit zaten aşağıdaki eski bölümde anlatıldığı için
> alt aralık kullanıldı.
> Bu commit'lerin **hiçbiri dağıtılan v2.2.0 tarball'ında yoktur**
> (`git describe --tags` → `v2.2.0-58-g4f25178`, ölçüldü 2026-10-17; ayrıca
> `RELEASE_READINESS.md` → "Kalan insan adımları").

### Added — v2.2.0 sonrası (feat, 3 commit)
- **security**: `api_v2` artık routable bind'i reddediyor; `serve-api` yanlış
  yapılandırmada temiz hata veriyor (`feat(security): api_v2 routable bind'i
  reddediyor; serve-api temiz hata veriyor`).
- **security**: RPC dosya yolları containment ile kapatıldı — `/etc`
  sızıntıları reddediliyor (`feat(security): RPC dosya yollari containment ile
  kapatildi`).
- **sbom**: gerçek SPDX-2.3 ve CycloneDX-1.6 çıkarımı; `.spdx.json` artık SPDX
  okuyucularla yeniden yüklenebiliyor
  (`feat(sbom): gercek SPDX-2.3 ve CycloneDX-1.6 cikarimi`).

### Fixed — v2.2.0 sonrası (fix, 29 commit)
- **desktop/arayüz**: modern arayüz her giriş noktasından açılıyor ve dosya
  `argv`'si artık webview'a ulaşıyor; GUI bayat gömülü sidecar'ı değil kurulu
  Python ağacını çalıştırıyor; `toast` timer'ı unmount'ta susuyor ve ikili
  yoksa kurulum artık uyarıyor; Tauri köprüsü yokken ham JS hatası yerine
  anlaşılır sebep; `tsc -b`'yi kıran TS2556 giderildi.
- **kuyruk / çok-örnek**: kuyruk kalıcılığı worker thread'lerde sessizce
  düşüyordu (`sqlite3` `check_same_thread`) ve tek-örnek devri kanallı kuyruk
  RPC'sine alındı; RPC yol ayrımı gerçekleşti, `atexit` çabuklaştı, SC2155
  giderildi.
- **i18n (12 commit)**: çekirdek modüllerin ve CLI/yardım/doktor çıktılarının
  kullanıcı metinleri kataloga alındı; JSON-RPC hata metinleri kullanıcının
  dilinde; uyumluluk kontrolünün AD ve MESAJ metinleri çevrildi (12 mesaj,
  9 yeni anahtar); EN kataloğundaki 127 yarı-Türkçe değer gerçek İngilizceye
  çevrildi; `tr()` konumlu-şablon `IndexError`'ını da yutuyor (çeviri CLI'i
  düşürmüyor); sekizli kaçış bozulması, eksik anahtarlar ve SBOM özeti
  çevrildi; CSV dışa aktarma başlığı çevrildi ve çeviri kalesi `ui/` +
  `config.py`'ye genişletildi; pacman yerel hatası ve polkit anotasyonu
  düzeltmeleri çeviriyle birlikte gitti.
- **güvenlik**: uzun yol girdisi CLI/RPC'yi düşürmüyor, glob enjeksiyonu
  kapandı; SBOM artık bütün dosya ağacını sınırsız dolanmıyor
  (`dep_resolver`/`security`).
- **derleme/analiz**: yerelleştirme ve PIE yüzünden SONSUZ kalan kütüphane
  analizi yeniden açıldı; dönüşüm CLI'i artık gerekçeyi de basıyor; düşürülen
  maintainer betikleri yüzeye çıkarıldı, ruff ve audit kapısı yeşile çekildi.
- **paketleme/AUR**: `.SRCINFO` gerçekten üretiliyor (üretilmiyorsa publish
  erken duruyor); `pkgforge-git` AUR paketi Tauri arayüzünü gerçekten
  derliyor ve kopya `mtime` yanıltması kapatıldı; PKGBUILD'in kendi kendisiyle
  çakışması ve `build/` artıklarının ignore dışında kalması giderildi;
  `pyproject` tablosu geri kondu, npm yığını tek parça yükseltildi, DNS'li
  fuzz testi çevrimdışı koşuyor.
- **CI/kurulum**: E2E harness'i hız-duyarlı kuyruk + teşhis ile düzeltildi;
  kendi-kendine-iyileşen kapı doğru kıyası baktı; `undici` 8.11.2'ye
  yükseltilerek high-severity audit bulguları temizlendi.

### Changed — v2.2.0 sonrası (chore + test + docs, 23 commit)
- **deps**: `uvicorn` 0.54.0 ve `pydantic` 2.14.1 tabanları (#34 + #48),
  `hypothesis` 6.168.5 ve `pyinstaller` 6.22.3 (#49), `fastapi` >= 0.143.0,
  `tomli` >= 2.5.0, actions grubu (6 güncelleme); Tauri yığını tek parça
  2.12'ye yükseltildi (#35–#39 yerine).
- **kapılar**: kapı araçları CI ile aynı sürüme sabitlendi, snapshot dalları
  %100'e tamamlandı; gerçek UÇTAN UCA harness artık CI'da koşuyor.
- **test (11 commit)**: dal-kesen birim test dalgası — `intake` 122,
  `cli` 72 + 21, `doctor` 57, `sbom` 81, `abi-scanner` 69, `score` 59,
  `dep-resolver` 46 + 60, `history_db` saniye-sınırı eşitliği ve `Convert`
  testindeki mock sızıntısı giderilmesi.
- **docs**: README durum rakamları yeniden ölçüldü (2026-10-14); akademik
  referanslar eklendi ve ölü rozet çapaları düzeltildi; tek-örnek kilidi
  denemesi ölçümleriyle kaydedildi (geri alındı); kalan adımlar ölçülmüş
  duruma göre yeniden yazıldı.

### Changed — gelir stratejisi sadeleştirme (2026-09-18)
- **Gelir modeli**: 3-aşamalı plan (sponsorluk → eşik → open core) tek
  katman pasif sponsorluğa indirgendi. 500/ay kurulum eşiği erişilemezdi
  (debtap 13 yılda 331 oy); Aşama 3 hosted katman mimariye ters (kullanıcı
  kendi sync URL'ini getirir). Kanıt: PEXT 2025 (hosted %40 daha hızlı,
  open core yavaş) + Alami et al. 2024 (sürdürülebilirlik kalite getirmez).
  Ayrıntı: `acik-kaynak-gelir-modeli.md` Bölüm 4.
- **Kripto ödeme kaldırıldı**: Giveth linki, 4 kripto cüzdan adresi ve
  `custom:` FUNDING.yml girdisi silindi — karar günlüğündeki "kripto
  checkout yok" ilkesiyle çelişiyordu. `DONATE_URL` artık
  `github.com/sponsors/goun7` (hesap açılınca). README "donations"
  terminolojisi "Sponsor" olarak düzeltildi.
- **Eski belgeler silindi**: `MONETIZATION_PLAN.md` ve
  `Açık Kaynak Gelir Modelleri Araştırması.md` tek yetkili belgede
  birleştirilmişti; artık gereksiz.

### Fixed
- **fix(launcher)**: `pkgforge` komutu projenin taşınması nedeniyle eski
  `~/Masaüstü/pkgforge` yoluna işaret ediyordu ve açılmıyordu (exit 2).
  `main.py`'ye `desktop` alt komutu eklendi: yerel/system Tauri ikilisini
  bulur, bulamazsa nedenini yazıp klasik PyQt6 arayüze düşer
  (`PKGFORGE_DESKTOP_BIN` ile geçersiz kılınabilir).
- **fix(install)**: `scripts/install.sh` artık önceden derlenmiş Tauri
  ikilisini ve sidecar'ı sistem kurulumuna kopyalıyor; menü girişi
  (`data/pkgforge.desktop`) `pkgforge desktop` çağırıyor.
- **fix(a11y)**: `DropZone` meşgul bayrağı `useRef`'ten `useState`'e
  alındı; artık `aria-busy`/`aria-disabled` raporluyor ve meşgulken
  odaktan çıkıyor (ZERON B2 bulgusu giderildi).
- **fix(docs)**: README/RELEASE_READINESS'de 2.1.0'e ve 2576 test sayısına
  takılı eski ölçümler 2026-09-17'deki gerçek ölçümlerle değiştirildi.
- **fix(leak)**: `tests/test_midband_round28.py` `HistoryDB._get_connection()`
  çağırıp bağlantıyı kapatmıyordu (`ResourceWarning: unclosed database`).
  `_conn()` bağlam yöneticisine alındı; tam suitte tracer ile
  **0/170 açık bağlantı** olarak doğrulandı.

### Changed
- **qa**: `pkgforge` traceback'leri eski `~/Masaüstü` yolunu gösteriyordu
  (proje taşınınca `.pyc` önbellekleri `co_filename`'i koruyor); proje
  `__pycache__`'i temizlendi.
- **assets**: swagger-ui build çıktıları `core/http_assets/swagger/`'dan
  `core/http_assets/dist/`'e taşındı. Bu dosyalar webpack ile derlenmiş
  minified üçüncü taraf paketleridir (`swagger-ui-bundle.js` 1.5 MB);
  `dist/` altında statik analiz araçları onları vendor build çıktısı olarak
  tanır. `/docs` offline (CDN'siz) çalışmaya devam eder; servis edilen
  bayt boyutları değişmedi (1.553.809 / 185.784).
- **a11y**: `Dialog` ve `CommandPalette` backdrop kapanması `onMouseDown`'dan
  `onClick`'e alındı; fareyi ve dokunmatik cihazları kapsar (önceden yalnızca
  fare).
- **cleanup**: eski oturum çalışma notları silindi (`findings.md`,
  `progress.md`, `QUALITY_SUMMARY.md`, `task_plan.md`); AI-araç
  yapılandırmaları (`.cursor/`, `.cursorrules`, `.vscode/`, `CLAUDE.md`)
  `.gitignore`'a alındı, repoya dahil edilmedi.

### Fixed
- **test**: `tests/test_privileged_helper.py` helper yolunu kaynak ağaca
  sabitliyordu; `find_privileged_helper()` kasıtlı olarak sistem öncelikli
  çözümler (polkit politikası yalnızca `/usr/share/pkgforge/scripts/`'i
  yetkilendirir). Kurulu her sistemde bu beklenti yanlış kalıp başarısız
  oluyordu; artık çözülen yolun geçerli/mevcut/çalıştırılbilir olduğu
  doğrulanıyor.

## [2.2.0] - 2026-09-09

### Added
- **desktop**: `externalBin` sidecar migrasyonu (shell plugin, triple-suffixed
  binary, capability scope `["serve"]`); CI'da gerçek `tauri build` + `.deb`
  artifact; release'e desktop `.deb` eki.
- **qa**: headless visual tour (`desktop/scripts/visual-tour.py`, 12 sayfa) +
  CI `visual-qa` job'u + README ekran görüntüleri.
- **test**: S3 kapatma paketi (46 eksik → kabul listeli azınlık), `.rpm`
  fixture canlı, hypothesis fuzz hedefleri (`test_s6_fuzz.py`), CSP e2e kilitleri.
- **ci**: action SHA-pinning, attest kapsamı (SBOM+SHA256SUMS+desktop),
  `release` environment, least-privilege checkout'lar, supply-chain job'u.
- **docs**: `SECURITY.md`, ADR-004/005, `docs/BENCHMARK_PARITY.md`,
  `docs/COVERAGE_GAPS.md` rewrite.

### Changed
- **typing**: `disallow-untyped-defs` basamak 1 (aşamalı; ikiz oturumla paralel).
- **i18n**: CLI kullanıcı-yolu tam tr/en (987 anahtar).

### Fixed
- **fix(rpc)**: `plugin.install` metodu METHODS'a bağlandı (desktop 404 alıyordu).
- **fix(provenance)**: `BuildProvenance.to_dict` yokluğu (mypy buldu; production AttributeError).
- **fix(compat)**: epoch'suz fallback, pacman-yok guard'ları, rpm2archive yedeği.

## [2.1.0] - 2026-09-07

### Added
- **gates**: `make verify` tek komutu + `[tool.coverage/ruff/mypy]` pinleri
  (`requirements-dev`: ruff==0.16.4, mypy==2.3.1); CI ile yerel aynı kapı.
- **ci**: `release.yml` gate job'u (ruff+mypy+bandit+tam suit) + her release'e
  SBOM (SPDX+CycloneDX) + SLSA provenance + SHA256SUMS; `supply-chain` job'u
  (pip-audit + pnpm audit); `arch-smoke` job'u (gerçek Arch container'da
  doctor + dry-run convert); sahte windows/macos matrix'i kaldırıldı.
- **test**: SSRF guard (15 test), i18n parite kilidi korunuyor (987/987).
- **docs**: `docs/adr/004-api-split.md`, `docs/adr/005-ssrf-confirm.md`,
  `docs/BENCHMARK_PARITY.md` (ölçülen PkgForge sayıları; debtap sütunu
  root `debtap -u` bekliyor).
- **packaging**: `packaging/aur/pkgforge-git/PKGBUILD` (+ `.SRCINFO`,
  namcap-temiz); branch protection (force-push/silme yasak).

### Changed
- **refactor(api)**: 1996 satırlık `core/api_server.py` →
  `core/api/{transport,handlers_*,registry,protocol,http}` + facade;
  `dir()` diff ile tam uyumluluk (`AS.transport`, `AS.handlers_queue`,
  `AS.http` kanonik yamalar).
- **i18n**: cli.py/main.py kullanıcı-yolu tam tr/en (794 → 987 anahtar);
  `--lang en` duman testli; quality grade + health skoru da yerelleşti.
- **security**: Tauri strict CSP (`csp: null` kapatıldı); SSRF deny-by-default
  (`allow_private_hosts` opt-in; ilk URL + her yönlendirme + marketplace +
  upstream HEAD); `plugin install` artık `--yes`/etkileşimli onay istiyor.
- **repo**: PUBLIC + topic/description vitrini; Polar.sh linkleri kaldırıldı
  (hesap yok); Giveth kripto bağışı eklendi.

### Fixed
- **fix(rpc)**: desktop'ın çağırdığı `plugin.install` metodu METHODS'ta yoktu
  (`Method not found`) — bölünme sırasında bulunup bağlandı.
- **fix(lint)**: ruff 7, mypy 2 (tarihsel "0 hata" iddiaları yanlıştı).
- **docs**: README sayıları ölçülen gerçeklere çekildi (2521 test:
  2514 passed + 5 skip + 2 çevresel fail; %99 kapsama; 95 dosya mypy).


### 2.1.0 öncesi birikmiş notlar (tarihsel, tek Unreleased'e birleşti)

#### Added
- **feat(deps)**: `core/maps.py` — Debian→Arch ad eşleştirme (`debian_dep_to_arch`,
  `DEB_DEP_MAP`: libc6→glibc, libstdc++6→gcc-libs, ...), lisans çözümleyici
  (`arch_license`: bilinen token→SPDX, bilinmeyen→dürüst `LicenseRef-<pkg>-unknown`),
  lisans stub yazıcı ve derleme sonlandırıcı (`finalize_build_output`).
- **feat(deps)**: betik yorumlayıcı taraması — `resolve_runtime_dependencies` artık
  shebang satırlarını da okur (`sh`→bash, `python3`→python, ...); betik-ağırlıklı
  paketlerde `dependency-detected-not-included` hatası kapanır.
- **docs**: tek dosya gelir modeli `acik-kaynak-gelir-modeli.md` (GitHub Sponsors +
  Polar.sh adım adım Ek A/B, mali müşavir kontrol listesi Ek C); Kreosus kaldırıldı;
  `MONETIZATION_PLAN.md` yönlendirmeye indirgendi; Tauri birincil UI ilanı.
- **test(maps)**: `tests/test_maps.py` (12 test: eşleştirme, lisans, stub, finalize,
  yorumlayıcı taraması).
- **test(ui)**: yarım kalmış async UI WIP'ine test uyarlaması — history uninstall/rollback
  testleri arka-plan thread'ini olay döngüsüyle bekler (`_pompala`); snapshot kaldırma
  testleri yeni yıkım-onay modalini Yes ile yanıtlar.
- **feat(ui)**: ResultDialog'a "🚀 Uygulamayı Aç" (Launch) butonu — read-only
  diyalogta çalıştırılabilir paket uygulamaları tek tıkla açılır
  (QDesktopServices; launch_requested sinyali; başarısızlıkta uyarı + tr/en).
- **test(i18n)**: anahtar-parite kilidi — lang_tr/lang_en anahtar kümeleri
  ve değer doluluğu her test koşusunda doğrulanır (5 test).

#### Changed
- **refactor(i18n)**: core/ içindeki 78 kullanıcı-yönelimli Türkçe log mesajı
  (34 dosya) tr() anahtarlarına taşındı; lang_tr/lang_en 545'er anahtar.
- **fix(ci)**: bandit adımındaki `|| true` kaldırıldı — güvenlik kapısı artık gerçek.
- **fix(packaging)**: üretilen PKGBUILD'ler url=/license=/sha256sums= yer
  tutucularını üstveriden alır (url="unknown", sha256="SKIP" yalnız üstveri
  yoksa); kaynak tarball'ı gerçek sha256 ile beslenir.
- **docs**: README coverage rozeti 100% → 99% (ölçülen gerçek değer);
  test sayısı 2428 collected'a güncellendi; progress.md'deki Tur-47..51
  Launch iddiaları dürüst düzeltme kayıtlarıyla netleştirildi.

#### Fixed
- **fix(packaging)**: üretilen her paket sistematik namcap ERROR alıyordu
  (`license=('custom')` → `unknown-spdx-license-identifier`; betik paketlerinde
  ek `dependency-detected-not-included`). Artık bilinen lisans SPDX'e çevrilir,
  bilinmeyen `LicenseRef-<pkg>-unknown` + dürüst `usr/share/licenses/<pkg>/UNKNOWN`
  stub'uyla paketlenir; shebang yorumlayıcıları `depends`e eklenir. Örnek: hello
  test paketi D→B, namcap çıktısı 2 hata→0 hata.
- **fix(compat)**: Debian bağımlılık adları (`libc6`, `libstdc++6`, ...) pacman ile
  birebir aranıp her pakette sahte WARNING üretiyordu. `DEB_DEP_MAP` normalizasyonu
  ile Arch karşılıklarına çevrilir; bilinmeyen adlar tahmin edilmeden raporlanır.
- **fix(ux)**: dönüştürülen paket `native_build/pkgout/` (veya `build/pkgout/`) altına
  gömülüyor, `src/`+`pkg/` artıkları dizinde kalıyordu. Artık ürün çıktı köküne taşınır,
  `src/`/`pkg/` temizlenir, `PKGBUILD` inceleme için saklanır.
- **fix(tests)**: yarım kalmış işlerin bozduğu 9 test onarıldı — history/tools dialog
  async WIP'i (3+2 test), main_window kapatma-davranışı değişikliği (1+1 yeni test),
  GPG stdin değişikliğine uymayan imza mock'ları, SecretStoreError içermeyen WebDAV
  stub'u, WORKSPACE_FILE ham atamasının sonraki testleri zehirlemesi.
- **fix(sync)**: keyring okuma hatası ham `RuntimeError` olarak fırlayıp senkronu
  öldürüyordu; artık yakalanıp parolasız devam edilir (sunucu reddederse `SyncError`).
  Düz-metin parola geri-dönüşü yasağı korunur; servis yoksa `available()` abort eder.
- **fix(ux)**: sudo/pkexec bombardımanı — delta/snapshot kurulumları tek işlemde
  4-5 ayrı parola diyalogu açıyordu. Yeni `write-batch` helper alt-komutu tüm
  dosyaları TEK pkexec diyaloğunda yazar; systemctl fiilleri (enable/start/
  stop/daemon-reload) artık helper üzerinden yetkili gider (eskiden yetkisiz
  çağrılıp sessizce başarısız oluyordu). Tam analiz: docs/SUDO_DENETIMI_FAZ14.md.
- **fix(packaging)**: gerçek polkit policy'si (`org.pkgforge.helper.policy`,
  auth_admin_keep) hiçbir yere kurulmuyordu — pkexec her çağrıda genel
  auth_admin fallback'ine düşüyordu. Artık wheel data-files + install.sh
  kuruyor; helper betikleri /usr/share/pkgforge/scripts'e root-0755 gider.
- **fix(delta)**: timer aralığı yok sayılıyordu (12 saat seçilse bile sabit
  6h OnCalendar). 24'ün bölenleri OnCalendar adımı, diğerleri OnUnitActiveSec.
- **fix(api)**: kurulum rotası doğrudan `pkexec pacman` yerine konsolide
  helper `install-pkg`'ye geçti (tek policy action + argüman doğrulaması).
- **test**: tek-diyalog sözleşmesi testlerle kilitlendi (write-batch çağrı
  sayısı = 1 assert'i; timer aralık yansıması; ret-kod yüzeyi).
- **feat(doctor)**: `pkgforge doctor` artık polkit teşhisi basıyor — policy
  kurulu mu, helper sisteme mi kurulu, kaynak ağacından mı çalışılıyor;
  "bolca sudo isteği" belirtisi görünür kök nedenine bağlanıyor.
- **feat(desktop)**: Doktor kartında Yetki (polkit) satırı: policy eksikse
  uyarı rengiyle teşhis detayı + tek-parola çözüm önerisi (install.sh) kutusu;
  kopyalanan tanı Markdown'ına `polkit.ok` bölümü düşer (tr/en).
- **fix(desktop)**: Settings: profil silme artık onaylı (ConfirmDialog — tek
  tıkla yıkıcı silme kalktı); Kaydet'in yanında "Kaydedilmemiş değişiklikler
  var" göstergesi (dirty-state; save/reset/import sonrası temizlenir).
- **fix(desktop)**: Convert: "Kuyruğu Temizle" artık onaylı — bekleyen tüm
  dönüşüm görevleri tek tıkla silinmiyor (Vazgeç = RPC yok; onay = queue.clear).
- **fix(desktop)**: Reports: snapshot temizlik servisi "Kaldır" işlemi (systemctl
  stop/disable + sistem dosyası silme) onaylı; Updates: delta zamanlayıcı
  "Kapat" işlemi onaylı (systemctl disable + dosya silme). i18n tr/en.
- **refactor(core)**: `score_package` 341 → 37 satır orkestratör; güvenlik/
  uyumluluk/üstveri/boyut denetimleri kategori fonksiyonlarına ayrıldı
  (davranış birebir; quality testleri 51/51, ruff+mypy temiz).
- **fix(desktop)**: PathPicker'da dialog reddi yakalanmıyordu — browse hatası
  yakalanmamış promise reddi üretiyordu; artık sessizce atlanıp kilit düşüyor.
- **test(desktop)**: kapsam %88.7 → %90.1: LogViewer %43.75→%84.37,
  SidecarGuard %53.84→%100, TopbarActions/PathPicker dalları, Dialog odak
  tuzağı + backdrop/başlıksız/odak-geri-dönüş (10/10). 552→557 test.
- **test(desktop)**: kapsam %90.1 → %92.86: Installed %54.47→%88.61
  (sıralama/CSV/sayfalama/temizle+geri-al/rollback), Sidebar %68.75→%100
  (kompakt mod/bölüm daraltma/localStorage hata dalı), Dialog %55.55→%93.33.
  557→571 test.
- **test(desktop)**: Faz 20b act() hijyeni: Convert/Updates render
  helper'ları async act flush; 36+ emit çağrısı await act'e çevrildi; sync
  testler async yapıldı. act uyarı 551→282 (kalanlar çok-tick promise
  zincirleri — test diagnostics'i, hata değil). 578/578, tsc 0.
- **test(desktop)**: Faz 20c: sekiz sayfa testine (Fleet/Tools/Reports/
  Export/Compare/Browse/Plugins/Security) aynı act reçetesi; WebDAV
  push/pull dalları Settings'te kapatıldı (sync.push/sync.pull + boş
  URL disabled). Uyarı 551→224; kapsam %93.1 (Settings %71.1); 580/580.
- **report**: Faz 21a kapanış değerlendirmesi — ruff 0, mypy 77 dosya
  0 hata, pytest rc=0 (~2460+ test), vitest 580/580, tsc 0, kapsam %93.1;
  act diagnostics 551→224; _temp_dir guard + WebDAV push/pull dalları.
- **refactor(core)**: Faz 18b dev fonksiyonlar — run_benchmarks 140→29
  (7 benç yardımcısı), verify_reproducible 132→~50 (extract/rebuild/compare),
  generate_sbom 123→~30 (4 yardımcı), install_auto_update 111→30
  (_find_systemctl/_auto_update_units/_write_and_enable_units). Kalan ≥100:
  6 (Handler fabrikası yanlış pozitif dahil).
- **refactor(core)**: Faz 18c: RpmConverterSubprocess._do_convert 106→~35
  (_rpm_extract/_rpm_security_gate/_rpm_makepkg_build/_find_pkg_artifact).
  Yanlış-sınıf düzenlemesi git-restore ile kurtarıldı. Kalan ≥100: 5
  (4'ü yeni tur adayı, _make_http_handler sınıf fabrikası — kabul).
- **refactor(core)**: Faz 18d: download_package 102→~80
  (_validate_download_url/_download_filename/_verify_download_sha256;
  HTTPS-zorunlu ve SHA teyit semantiği aynen). Kalan ≥100: 4 kabul
  (şablon üreteci + sınıf fabrikası) + 2 hafif aday.
- **refactor(core)**: Faz 18e: check_abi_compatibility 103→~55
  (_extract_pkg_for_abi/_collect_elf_binaries/_ldd_missing_libs) ve
  build_file_dep_graph 100→~55 (_extract_for_graph/_graph_elf_candidates/
  _ldd_graph_edges). ≥100 satır envanteri KAPANDI — kalan 2 kabul
  edilmiş (PKGBUILD şablon üreteci 112; Handler sınıf fabrikası 138,
  iç metodlar ≤31).
- **test(desktop)**: Faz 22 kapanış cilası: Settings yedek-yolu onChange +
  sync.export, WebDAV user/pass yazımı (+2 test). Convert browse-diyalog
  testine flaky koruması (explicit flush + 5s waitFor). 580→582 test,
  kapsam %93.1→%93.22.
- **refactor(core)**: Faz 20 dev fonksiyonlar bölündü — davranış birebir:
  _run_pipeline 206→43 satır (_stage_security/_stage_malware/_stage_analysis/
  _stage_conversion); serve_http 175→33 (_http_validate_bind +
  _make_http_handler fabrikası); _check_shared_libraries 144→76
  (_list_package_elf_files + _analyze_elf_dependencies + _shared_lib_result,
  ldd yasağı korunur).
- **test(desktop)**: kapsam %92.86 → %93.06: Settings %68.44→%70.22
  (profil hata yolları/radio geçişi/sync.import/sync.config/dbus başlat ve
  yok durumu). 571→578 test.

#### Fixed
- **fix(desktop)**: abonelik unmount yarışı — `onEvent().then(push)` deseni
  erken unmount'ta sızıyordu; `rpc.ts`'de yeni `eventBinder()` ile 10 sayfa
  güvenli desene migrate edildi (33 çağrı noktası). Handler catch'lerinde
  bırakılan 9 tek-seferlik abonelik de kapatıldı.
- **fix(desktop)**: Browse abonelik effect'i her render'da kopup yeniden
  kuruluyordu (kararsız `t` bağımlılığı) — deps `[toast, lang]`.
- **fix(core)**: `subprocess_converters` ar/tar borusunda ar stderr okunmuyor-
  du → 64KB boru dolunca ölümkilit; ar/tar returncode kontrolü de yoktu
  (sessiz bozuk çıkarım). native_deb_converter parite deseni uygulandı.
- **test(desktop)**: `rpc.test.ts` eventBinder birim testleri (4); Python
  ar/tar hata-yolu testleri (2).

## [2.0.0] - 2026-08-27

### Added
- **feat**: Feature Tezgâhı Faz 2 — kalan CLI özellikleri `scan-image`,
  `attest`, `publish`, `snapshot-cleanup` her iki GUI'ye taşındı
  (`tools.*` RPC + PyQt6 4 sekme + Tauri 4 kart + `core.scan_oci_image`).
- **feat**: Fleet/kurumsal konsol (Alan D) — F5.18 sync backends (webdav/
  git/rclone-s3 + age) ve F5.19 politika motoru tek `fleet.status` RPC'sinde
  birleşti; PyQt6 FleetDialog + Tauri Fleet sayfası (backend/policy/profil/
  senkron özeti ve push/pull/export eylemleri).
- **feat**: UX modernizasyonu — 2026 standartları: motion tokenları,
  `prefers-reduced-motion` desteği, `focus-visible` klavye erişilebilirliği.

### Changed
- **test**: mutmut kalite kampanyası — `core/installer.py` mutant öldürme
  oranı **%34 → %99.1** (229 mutant / 227 öldürüldü; kalan 2 kanıtlanabilir
  eşdeğer mutant). FakeProcess + kesin-assert/argüman-yakalama testleri.

### Added (önceki)
- **support**: Gelir/bağış katmanı — `.github/FUNDING.yml` (GitHub
  Sponsors + Polar.sh + Kreosus), About dialoguna "Destek Ol" butonu
  (`config.DONATE_URL`), README destek bölümü, issue şablonları
  (bug/feature/config) ve strateji belgesi MONETIZATION_PLAN.md.

### Security
- **fix**: install_rehearsal container içi `sh -c` komutuna paket adı/klasörü
  quote'suz gömülüyordu (CWE-78) — shlex.quote ile kapatıldı; tam denetim
  SECURITY_REVIEW.md'de.

### Changed
- **refactor**: QProcess kullanan 5 sinifa (deb/rpm/native_deb donusturucu,
  installer, distrobox_fallback) process_factory enjeksiyonu — testler
  somut QProcess yerine sahte surec verebilir.
- **fix**: sessiz `except: pass` bloklarina debug log eklendi (abi_scanner,
  aur_publish, benchmark, dbus_service, dep_graph, from_source);
  `_estimate_size_mb` okunamayan girdiyi tum tahmini bozmak yerine
  atlayip logluyor; `find_privileged_helper` fallback'te uyari veriyor.
- **chore**: diger oturumun bekleyen kozmetik duzenlemeleri commit edildi
  (7c79ac7).


### Added
- **tests**: Oturum-3 100/100 taramasi — package_signing, cli_bridge,
  capabilities, upstream_tracker, benchmark, snapshot_manager,
  offline_cache %100; privileged/distrobox/cloud_sync/rehearsal/
  structured_log/sigstore/aur_publish/rpm-flatpak-appimage donusturuculeri,
  styles, snapshot_cleanup, oci_builder, delta_updater, profiles,
  queue_manager, provenance, sbom, aur_checker kalan dallari (+142 test);
  toplam kapsama **%97 → %100** (10 541 stmt, **0 eksik**), **2147 test**.
- **tests**: Oturum-2 final sprint — api_server %100,
  compatibility_checker %100, abi_scanner %100, installer %100,
  dbus_service %100, cve_scanner %100, secrets_store/plugins %100
  (+~90 yeni test); toplam kapsama **%89 → %97** (10 541 stmt,
  307 eksik), **2005+ test**.