# Task Plan: PkgForge — Kritiksizlik Taraması (goal-4bc2fb3f-d552-4e47-ba14-a91ae050191a)

## Hedef
Kullanıcı talebi: 50 tur otonom tarama; hiçbir eleştiri/öneri/fikir kalmasın;
tüm kalite kapıları yeşil ve dokümantasyon gerçek sayılarla tutarlı.

## Tur 1 — Bulunanlar ve Durum
- [x] tests/test_api_server_core.py (önceki oturumdan kalan untracked): 2 kırmızı test → düzeltildi
      - _validate_aur_name ".." / "-bas" kabul ediyordu → ilk-karakter alfanumerik kuralı (traversal kapanışı)
      - rate_limiter testi pencere semantiğini yanlış varsayıyordu (now+999) → now+60
- [x] ruff 31 hata → 0 (11 test dosyasında F841/RUF059/C408/RUF012/B023 temizliği)
- [x] mypy 1 hata (main.py token_file getattr) → 0 (isinstance daralması)
- [x] git'te izlenen çöp dosya 'https:/github.com/deneme/proje/CMakeLists.txt' → git rm
- [x] desktop/package.json'da test script'i yoktu → "test": "vitest run" eklendi; 74 test yeşil, tsc build temiz
- [x] CI cov gate yükseltildi (CI-parite yerel kapı; ölçüm %96)
- [x] README badge + gövde sayıları gerçek değerlere çekildi (2005 test / %96)
- [x] CHANGELOG Unreleased: tüm sprint maddeleri işlendi
      (AUR-name hardening, rate-limiter, lint/mypy sıfır, wheel+E2E kanıtı)
- [x] RELEASE_READINESS.md oluşturuldu: ölçümlü tablo + %100 modül listesi
      (20 modül; api_server/compat/abi dahil)
- [x] progress.md her tur için kaydediliyor
- [x] Tam doğrulama: mypy 0 / ruff 0 / bandit 0 / rc=0 / wheel+E2E ✓

## Kurallar
- Her iddia komutla doğrulanır (verification-before-completion)
- Bulgular findings.md / progress.md'ye yazılır

---

# Denetim Düzeltme Planı — 4 İş Paketi (goal devamı; kullanıcı onayı: 4 paket)

## Durum Özeti (denetim taraması bulguları)
- master @ c6702d0, 32 commit push EDİLMEDİ.
- Dürüst denetim bulguları: (1) ResultDialog Launch butonu yok ama d503ee8/progress.md:590-622 "var" diyor;
  (2) core/ içinde 181 kullanıcı-görünür sabit TR string, 34 dosya; (3) README coverage-100% etiketi gerçek ölçümle doğrulanmadı;
  (4) CI bandit adımı `|| true` ile hiç düşmez; (5) PKGBUILD url/license/sha256 yer tutucuları; (6) 32 commit push edilmemiş.

## Faz A — ResultDialog Launch butonu (TDD, inline) [in_progress]
- Seam: ResultDialog(read_only=True, metadata=...) + findChildren(QPushButton) + launch_requested(str) sinyali + _on_launch().
- Tasarım: read_only+yeniden açılışta, metadata.name çalıştırılabiliri shutil.which ile bulunuyorsa "🚀 Uygulamayı Aç" butonu;
  click → QDesktopServices.openUrl(QUrl.fromLocalFile(path)) + launch_requested.emit(path); başarısızsa warning.
- Anahtarlar: result.launch_btn, result.launch_failed (tr/en).
- Testler: görünür/kapalı/yol yok/openUrl False. Mevcut testler which() None döndüğü için etkilenmez.

## Faz B — Beyanları gerçeğe eşitle [TAMAM — Tur-53]
- progress.md 590/598/606/614/622: "ResultDialog'da 'Aç/Launch' butonu" → dürüst düzeltme kaydı + yeni Tur kaydı.
- README coverage etiketi → yerel ölçüm sonucuyla değiştir (ölçüm arka planda çalışıyor).
- Commit mesajı d503ee8 düzeltilemez (hash zinciri) → progress.md'de dürüst düzeltme kaydı.

## Faz C — CI güvenlik kapısı + PKGBUILD yer tutucuları [TAMAM — Tur-53]
- test.yml:74 `|| true` kaldır.
- intake.py generate_binary_pkgbuild + kaynak şablonu: url= (metadata.url), sha256 (gerçek tarball hash), license_id parametresi.
- Çağrıcıları meta.url + gerçek hash ile besle; testleri güncelle.

## Faz D — core/ i18n [TAMAM — Tur-53; subagent'lar düşündü → mekanik AST transformer]
- Gerçekleşme: 34 dosyada 78 log çağrısı (log.info/warning/... + print) tr()'e çevrildi
  (.spec-work/i18n-batches/transform.py ile AST-tabanlı güvenli dönüşüm; f-string/{format} kalmadı).
- 78 yeni anahtar hem lang_tr.py hem lang_en.py'ye eklendi (545/545 parity).
- tests/test_i18n_parity.py: 5 test (parity + nonempty + tam çözüm + unknown-fallback + placeholder).
- Batch'ler dosya bazında; ortak durum (lang_tr.py/lang_en.py) MERKEZİ: subagent'lar kendi
  .spec-work/i18n-batch-N.json dosyasına anahtar çiftleri yazar, ben birleştiririm → çakışma yok.
- Anahtar öneki modül bazlı (delta.*, quality.*, flatpak.* ...); lang_tr.py'de varolan aynı-metin anahtarları yeniden kullanılır.
- Her batch kendi dosyalarında ruff + test grep; anahtarlar birleşince tam suit.
- Parity kilidi: set(lang_tr)==set(lang_en) testi ekle.

## Faz E — Kapılar + commit + push [TAMAM — Tur-53]
- ruff ✅ (0 hata), mypy ✅ (311 dosya, 0 hata), bandit ✅ (0 medium/high severity),
  pytest ✅ (exit 0, 2 ağ-skip'i), vitest ✅ (582/582), tsc+vite build ✅.
- README: coverage 99%, tests 2428 collected (gerçek ölçüm).
- Commit + push: bu tur sonunda yapılır.

## Notlar
- pytest addopts -q → özet satırı yok; sayılar --collect-only veya nokta sayımıyla.
- Modal QMessageBox engeli: launch prompt flag-gated (c6702d0) — yeni buton testleri modal açmaz.
- .venv/bin/ python zorunlu (sistem python bozuk).
