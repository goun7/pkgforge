# Faz 3 — Alan C: Mimari Genişleme (Design Spec)

> Tarih: 2026-08-22 · Durum: ONAYLI (kullanıcı "Başla" ile Faz 3'ü başlattı)
> Bağlayıcı: docs/ROADMAP.md C1–C3 maddeleri

## 1. Kapsam ve İlkeler

C1–C3 mimari genişleme. **Temel ilke:** PkgForge harici Python bağımlılığı olmadan
çalışır (yalnızca stdlib + sistem araçları). Bu nedenle:
- **C1 D-Bus:** jeepney *opsiyonel* bağımlılık; yoksa zarif hata. REST kısmı F2.6'da tamamlandı.
- **C3 Bulut:** WebDAV stdlib urllib ile; kimlik bilgisi yoksa/erişilemezse zarif bozulma.
  Yerel zip yedekleme her zaman çalışır.

## 2. Sidecar Method Sözleşmesi

### C1 — D-Bus servisi (REST zaten var)
| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| dbus.status | {} | {available, running, bus_name} | hayır |
| dbus.start | {} | {started} → event/dbus_done | evet |

Yeni core: `core/dbus_service.py` — jeepney ile session bus'ta
`org.pkgforge.App` / `/org/pkgforge/App` adını alır; aynı METHODS dict'ini
`Call(method, params_json)` üzerinden üçüncü taraflara açar. jeepney yoksa
`dbus.status` {available:false} döner, `dbus.start` hata verir.

### C2 — Çoklu profil
| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| profile.list | {} | [{name, active}] | hayır |
| profile.current | {} | {name} | hayır |
| profile.create | {name} | {ok} | hayır |
| profile.switch | {name} | {ok} | hayır |
| profile.delete | {name} | {ok} | hayır |

Yeni core: `core/profiles.py`. Profiller `CONFIG_DIR/profiles/<name>/` altında
kendi `settings.json` + `history.db`'sini tutar. Aktif profil `CONFIG_DIR/active_profile`
dosyasında saklanır. Varsayılan profil "default" (mevcut ayarlar taşınmaz, boş başlar).
Geçişte settings/history yolu yeniden bağlanır.

### C3 — Bulut senkronizasyonu / yedekleme
| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| sync.export | {output_path?} | {ok, path} | evet |
| sync.import | {backup_path} | {ok, restored} | evet |
| sync.webdav_push | {} | {ok} → event/sync_done | evet |
| sync.webdav_pull | {} | {ok} → event/sync_done | evet |
| sync.config | {url?, username?, password?} | {ok} | hayır |

Yeni core: `core/cloud_sync.py`.
- `export_backup()`: settings.json + history.db + profiles/ → tek .zip (stdlib zipfile).
- `import_backup()`: zip'i doğrulayıp CONFIG_DIR'e geri yükler.
- `webdav_push/pull()`: stdlib urllib ile WebDAV PUT/GET; ayarlardan
  `sync_url/sync_username/sync_password` okur. Yoksa/erişilemezse zarif hata.

## 3. Frontend Değişiklikleri

- **Settings** genişletme:
  - "Profiller" kartı (C2): profil listesi, oluştur, geçiş yap, sil.
  - "Yedekleme & Senkronizasyon" kartı (C3): zip dışa/içe aktar, WebDAV yapılandırma + push/pull.
- **Reports** veya Settings: D-Bus durumu kartı (C1) — "D-Bus servisi" başlat/durum.

## 4. Test Stratejisi
- Python: her yeni modül için unit test (jeepney/WebDAV ağ bağımlı olanlar mock/offline).
- Frontend: Settings genişletmeleri için vitest (mock rpc).
- Regression: 686 Python + 57 vitest yeşil kalacak.

## 5. Uygulama Sırası
| # | Milestone | Kapsam |
|---|-----------|--------|
| F3.1 | C2 Çoklu profil | core/profiles.py + profile.* + Settings kartı |
| F3.2 | C3 Yedekleme/Senkron | core/cloud_sync.py + sync.* + Settings kartı |
| F3.3 | C1 D-Bus | core/dbus_service.py + dbus.* + durum kartı |
| F3.4 | Entegrasyon + ROADMAP + push | full suite, E2E, tag |

## 6. Kısıtlar
- Mevcut token/design system; Türkçe UI; repo PRIVATE.
- Harici bağımlılık ZORUNLU değil: jeepney/WebDAV opsiyonel, zarif bozulma.
- Profil geçişi sidecar'ın settings/history yolunu runtime'da yeniden bağlar.
