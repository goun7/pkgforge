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
5. Kök `PKGBUILD` `sha256sums`, tag tarball'ının yeniden indirilmesiyle
   güncellenir/yeniden doğrulanır. Komut (v2.2.0 için ölçüldü 2026-10-17 —
   `1b4639c8baef8277afcde345154fb8c1e6ed42d2a6e15df11b59deb6d3aaec8b`,
   4 174 629 bayt; kök `PKGBUILD:60` ile birebir aynı):

   ```bash
   curl -sL https://github.com/goun7/pkgforge/archive/refs/tags/vX.Y.Z.tar.gz \
     -o /tmp/vX.Y.Z.tar.gz
   sha256sum /tmp/vX.Y.Z.tar.gz   # PKGBUILD sha256sums ile kıyasla
   wc -c    /tmp/vX.Y.Z.tar.gz
   ```

   **`namcap` "temiz" değildir — ölçülen sonuç 0 hata / 471 uyarı** (AUR
   `pkgforge-git` derlemesi, 2026-10-16; uyarıların 454'ü namcap'ın kendi
   modüllerimizi "core.*"/"ui.*" dış bağımlı sanmasından). Yeniden ölçüm:
   `namcap pkgforge-git-*.pkg.tar.zst > /tmp/namcap.log; grep -cE '^E: ' /tmp/namcap.log; grep -cE '^W: ' /tmp/namcap.log`.
   İki koşul: (i) `namcap` `depends` değil **`optdepends`** satırıdır
   (`grep -n "optdepends" -A12 PKGBUILD`) — kurulu olmayan sistemlerde analiz
   çalışmaz ve rapor "namcap bulunamadı, statik analiz atlandı" der;
   (ii) 0 hata eşiği bir kabul kapısıdır, 471 uyarı "paket sorunsuz" anlamına
   gelmez.
   Ayrıca `pkgforge-git` derlemesi `makepkg --skipinteg` ile koştu; bu bayrak
   bütünlük kontrollerini **atlar**, dolayısıyla o koşum "girdileri doğrulanmış
   derleme" kanıtı değildir.
6. AUR: `packaging/aur/pkgforge-git` (her zaman) + stable `pkgforge`
   (tag sonrası, sha256 ile) — AUR hesabı + ssh gerekir (insan adımı).

## Yasaklar

- Testsiz publish yok (`release.yml` gate'i atlanamaz).
- Rozet/sayı elle yazılmaz (`make verify` çıktısı kopyalanır).
- `master`'a force-push yok (branch protection zaten kilitli). Depolunun
  varsayılan dalı `main` değil **`master`**'dır (ölçüldü 2026-10-17:
  `git symbolic-ref refs/remotes/origin/HEAD` → `refs/remotes/origin/master`).
