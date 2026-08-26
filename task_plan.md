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