# Faz 5 — Güvenlik, Dürüstlük, Mimari ve Ürün (TAM KAPSAM)

Kaynak: Faz 4 sonrası ikinci acımasız eleştiri (5 başlık) + 20 yaratıcı öneri.
İlke: sömürülebilir güvenlik açıkları → ölçüm dürüstlüğü → mimari borç → ürün.
Her madde kendi test(ler)iyle, ayrı commit'le. Kırılgan maddeler risk notu taşır.

Eleştiriler C1–C20, öneriler S1–S20 olarak numaralandı; her F5 maddesi hangisini
kapattığını taşır. Kapsamda olmayan hiçbir eleştiri/öneri kalmaz.

---

## A. Güvenlik Çekirdeği

**F5.1 Tek Yetki Kaynağı (capabilities)** — C1, S1
- `core/capabilities.py` + `capabilities.json`: HTTP operator/reader metodları,
  D-Bus read/mutate listeleri ve polkit action id'leri TEK dosyadan türetilir.
- D-Bus arayan doğrulaması: mutations açıkken jeepney
  `GetConnectionUnixUser` ile aynı-UID kontrolü; farklı kullanıcı → -32002 reddi.
- `privileged.build_policy_text` bu modülü kullanır (drift imkânsız).
- Kabul: üç yüzey tek kaynaktan; arayan-UID monkeypatch testleri; XML şema testi.

**F5.2 Taşıma Güvenliği** — C2, C3, C6, S2
- `--token-file` + `PKGFORGE_TOKEN` env (token artık ps'te görünmez).
- LAN bind'da TLS yoksa açık `--allow-insecure-http-lan` bayrağı zorunlu
  (WebDAV standardıyla uyum; sertifika üretimi openssl CLI varsa belgelenir).
- `X-Forwarded-For` yalnızca `--trusted-proxy` bayrağıyla dikkate alınır.
- Rate-map budama: >4096 IP görüldüğünde boş deque'ler silinir (bellek üst sınırı).
- Kabul: token-file/env 401-200 testleri, prune testi, XFF testi.

**F5.3 systemd Sandbox Üreteci** — C20, S3
- Unit'e: TimeoutStartSec=300, NoNewPrivileges=true, ProtectSystem=full,
  PrivateTmp=true, ReadWritePaths=%h/.config/pkgforge, MemoryMax=1536M.
- Bilinçli kısıt: NoNewPrivileges nedeniyle headless *kurulum* görevi yok
  (TASKS zaten salt dönüşüm/tarama); belgeye not düşülür.
- Kabul: yönerge varlık testleri.

**F5.4 pkexec Konsolidasyonu** — C4, S4
- `scripts/install_helper.sh` → alt komutlu `pkgforge-privileged.sh`
  (install-pkg / write-root-file / systemctl-enable); delta_updater,
  snapshot_manager, snapshot_cleanup bu arabirime geçer; action id'leri
  F5.1 capabilities'ten gelir.
- Risk: çalışan yetkili akışlarda davranış değişimi → her modül için komut
  kurgulama unit testleri zorunlu.

**F5.5 CDN Bağımsızlığı** — C5, C17(kısmen)
- swagger-ui vendor edilir (Apache-2.0) ve `core/http_assets/` altından
  statik servis edilir; docs/dashboard offline çalışır; CSP meta eklenir;
  CDN kalırsa SRI zorunlu.
- Kabul: internet olmadan docs/dashboard 200 + içerik testi.

## B. Test ve Ölçüm Dürüstlüğü

**F5.6 Keyring Canlı CI** — C8
- Yeni CI job: dbus-run-session + gnome-keyring-daemon altında
  Secret Service canlı testi koşar (skip yalnız yerelde).
- Risk: jeepney marshalling'i ilk kez gerçekten doğrulanacak; bulunacak
  hatalar düzeltilir — bu madde bilinçli olarak "keşif" içerir.

**F5.7 Arşiv Fuzz** — C10
- hypothesis: traversal adları, mutlak yol, sahte manifest, kesik üye,
  ZIP bomba-vari boyutlar. İnvariant: SyncError dışında profil dizini
  dışına yazma yok, yarım yazma yok.

**F5.8 Mutation Testing Pilotu** — C10
- mutmut, kapsam: `core/pipeline.py` karar kapısı +
  `core/installer.py` argüman doğrulama. Skor ROADMAP'e işlenir; CI dışı.

**F5.9 Legacy Lint Sıfırlama** — C14
- 83 ruff bulgu elle kapatılır; CI ruff job'ı `ruff check .` genişliğine çıkar.

**F5.10 Ölçüm Dürüstlüğü** — C11, C13, C7
- parity testine Cargo.toml eklenir; badge koşulu sahibi `goun7` düzeltilir
  (ölü job onarımı); cov-fail-under 48→55; ROADMAP'e ≥%70 hedefi yazılır.

## C. Mimari

**F5.11 api_server Bölünmesi** — C16, C17
- `core/http_api/` paketi: handler + routers/{meta,queue,profiles,sync,
  dbus,schedule,plugins,compare}.py; METHODS kaydı fonksiyonlara bölünür;
  gömülü HTML'ler `core/http_assets/` dosyalarına taşınır.
- `core/api_server.py` facade olarak kalır — mevcut testler değişmeden geçer.

**F5.12 Kuyruk Kalıcılığı + Model Birleşimi** — C19, C18
- sqlite journal (id, path, status, priority, message); restart'ta pending
  öğeler geri yüklenir; interaktif `_pipeline` singleton'ı registry'ye
  kademeli yaklaştırılır.

**F5.13 METHODS→TS Codegen** — S5'in derinleştirmesi
- `tools/gen_api_ts` → `desktop/src/lib/api-types.ts` (metod adları + event
  payload union); vitest tip-smoke; CI'da "üretilen dosya güncel mi" diff-check.

## D. Ürün / Yaratıcı

**F5.14 Kurulum Provası** — S9: distrobox/OCI altyapısıyla konteyner içi
kurulum simülasyonu, dosya-liste diff'i GUI'de; RPC `install.rehearse`.
**F5.15 Provenance Makbuzu** — S10: input sha256 + debtap-db tarihi + araç
sürümleri attest/SBOM'a gömülür.
**F5.16 Delta Güncellemeler** — S11: xdelta3/bsdiff opsiyonel; araç yoksa
özellik kapalı gelir. DENEYSEL etiketli.
**F5.17 Restore Tatbikatı** — S12: TASKS'e `restore_drill` — tmp HOME'a
export→import→hash karşılaştırma; zamanlanabilir.
**F5.18 Fleet Sync** — S13: backend soyutlama (webdav | git | rclone-s3);
age CLI varsa uçtan-uca şifreleme; anahtarlık entegrasyonu hazır.
**F5.19 Politika Motoru** — S14: profil bazlı compat eşikleri
("WARNING'de blokla"); Settings'e seçici.
**F5.20 i18n Tamamlama** — C12: Convert canlı dil; sözlük genişletilir;
vitest güncellenir.
**F5.21 AppStream/Flathub** — S15: appstream metaveri + flatpak-builder
manifesti (deneysel).
**F5.22 `pkgforge doctor`** — S16: health + tools.status + debtap/pkexec/
keyring durumu tek teşhis çıktısı.
**F5.23 SSE Olay Akışı** — S17: `GET /events` (reader token) → pano canlı log.
**F5.24 Stats Wrapped** — S18: yıllık dönüşüm raporu (CLI + RPC).
**F5.25 Upstream Enrichment** — S19: from-source akışında otomatik
description/license doldurma.
**F5.26 Perf Bütçesi** — S20: benchmark job'ına baseline karşılaştırma;
%20 sapma fail.

---

## Dalga Planı
1. **Dalga 1 (hemen):** F5.0 plan + hızlı kazançlar — F5.3, F5.2'nin
   prune/token-file kısmı, F5.10'un badge+Cargo.toml kısmı.
2. **Dalga 2:** F5.1, F5.5, F5.6 (güvenlik çekirdeği + keyring keşfi)
3. **Dalga 3:** F5.9, F5.11, F5.12 (borç temizliği)
4. **Dalga 4:** F5.2-TLS/XFF, F5.4, F5.7, F5.8, F5.13, F5.20
5. **Dalga 5:** F5.14–F5.26 ürün bloğu

## Riskler
- Keyring marshalling gerçek bus'ta ilk kez sınanıyor (F5.6) — bulgular
  düzeltilerek kapatılır, skip'e sığınılmaz.
- api_server split regresyonu → facade + testlerin değişmemesi şartı.
- Delta/Flatpak deneysel: varsayılan kapalı gelir, ROADMAP'de etiketlenir.
