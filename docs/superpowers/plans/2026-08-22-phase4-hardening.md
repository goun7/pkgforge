# Faz 4 — Sertleştirme & Dürüstlük Implementation Plan

> Kaynak: son-durum acımasız eleştirisi + fikir listesi (kullanıcı onaylı: "Önem sırasına göre bütün maddeleri planla ve gerçekleştir")

## Önem sırası ve milestone eşlemesi

| Öncelik | Eleştiri/Fikir | Milestone |
|---------|----------------|-----------|
| P0-1 | Event sözleşme testi (Tauri charset + emit/listen çapraz) | F4.1 |
| P0-2a | HTTP: non-loopback'te token zorunlu, gövde limiti, rate limit, GET /health | F4.2 |
| P0-2b | D-Bus: read-only varsayılan policy + dbus.set_policy | F4.2 |
| P0-3 | Batch paralellik dürüstlüğü: pipeline kayıt defteri (item_id → instance) | F4.3 |
| P1-4 | Keyring: Secret Service (jeepney), WebDAV şifresi migrasyonu | F4.4 |
| P1-5(9) | Yedek bütünlüğü: wal_checkpoint + sha256 manifest + atomik restore | F4.5 |
| P1-6 | systemd user timer + pkgforge schedule-run + install-timer | F4.6 |
| P1-7 | Polkit helper betiği + .policy + install.start kablolaması | F4.7 |
| P2-8 | OpenAPI otomatik şema + /openapi.json + /docs Swagger | F4.8 |
| P2-9 | Tek dosyalık web dashboard (GET /) | F4.9 |
| P2-10 | GitHub Actions CI + sürüm tek kaynak parity testi | F4.10 |
| P2-11 | i18n köprüsü (Settings kartları tr/en canlı geçiş) | F4.11 |

## Kurallar
- Her milestone: önce test → uygulama → ilgili süit yeşil → ayrı commit.
- Sıfır yeni zorunlu bağımlılık; opsiyoneller zarif bozulur.
- Tam regresyon F4.5 ve finalde koşulur; E2E finalde.

## Definition of Done
Eleştirinin 12 maddesinin her biri ya kodda çözülmüş ya da dürüstçe yeniden kapsamlandırılmış olur.