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
- [ ] CI cov gate 48 → 72 yükselt (ölçüm 76%)
- [ ] README badge'leri + gövde sayıları gerçek değerlere çekilecek (bekleyen: pytest -rs kesin sayım)
- [ ] CHANGELOG Unreleased: AUR-name hardening + rate-limiter test + lint/mypy sıfırlama + desktop test script maddeleri
- [ ] docs/RELEASE_READINESS.md ölçümlü durum tablosu + skor tablosu tazeleme
- [ ] progress.md tur kaydı
- [ ] Tam doğrulama + commit

## Kurallar
- Her iddia komutla doğrulanır (verification-before-completion)
- Bulgular findings.md / progress.md'ye yazılır
