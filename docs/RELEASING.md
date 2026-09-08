# Sürüm Yayınlama Runbook'u (RELEASING)

## Tag disiplini

- Format: hafif (lightweight) tag değil, **annotated tag**: `git tag -a vX.Y.Z -m "..."`.
- Tag **taşınmaz**: bir kez push'lanan tag aynı isimle başka commit'e alınmaz.
  Yanlış tag → yeni patch sürümü (`vX.Y.(Z+1)`), asla `--force`.
- Geçmiş notu (dürüstlük): `v2.1.0` geliştirme sırasında CI yeşillenene kadar
  4 kez taşındı — o zaman yayınlanmış artifact yoktu ve boru hattı kırmızıydı.
  Bu kural o deneyimden doğdu; `v2.2.0`'dan itibaren geçerlidir.
- İmza durumu: tag'ler **imzasız** (proje GPG anahtarı yok). Intensiyon:
  SLSA provenance + SHA256SUMS release güvencesini taşır; GPG tag imzası
  anahtar kurulunca eklenecek (S7 sonrası backlog).

## Sürüm akışı

1. `CHANGELOG.md` Unreleased → sürüm başlığına çevrilir, sayılar `make verify`
   çıktısıyla yazılır (tahmin yasak).
2. Versiyon 5 yerde eşitlenir: `pyproject.toml`, `config.APP_VERSION`,
   `desktop/package.json`, `desktop/src-tauri/tauri.conf.json`,
   `desktop/src-tauri/Cargo.toml` (`tests/test_version_parity.py` kilitler).
3. `git tag -a vX.Y.Z && git push origin vX.Y.Z` → Release workflow:
   gate → build (wheel/sdist+SBOM) → desktop (.deb) → publish.
4. Release sayfasında asset kontrolü: `*.whl`, `*.tar.gz`, `*.spdx.json`,
   `*.cyclonedx.json`, `SHA256SUMS`, `*.deb` (+ desktop SHA256SUMS).
5. Kök `PKGBUILD` `sha256sums` tag tarball'ından güncellenir
   (`curl -sL .../refs/tags/vX.Y.Z.tar.gz | sha256sum`, `namcap` temiz).
6. AUR: `packaging/aur/pkgforge-git` (her zaman) + stable `pkgforge`
   (tag sonrası, sha256 ile) — AUR hesabı + ssh gerekir (insan adımı).

## Yasaklar

- Testsiz publish yok (`release.yml` gate'i atlanamaz).
- Rozet/sayı elle yazılmaz (`make verify` çıktısı kopyalanır).
- `main`'e force-push yok (branch protection zaten kilitli).
