# Faz 2 — Alan B: Yeni Yetenekler (Design Spec)

> Tarih: 2026-08-22 · Durum: ONAYLI (kullanıcı "Devam et" ile Faz 2'yi başlattı)
> Bağlayıcı: docs/ROADMAP.md B1–B8 maddeleri

## 1. Kapsam

B1–B8 yeni yetenekler. Hazır kod olanlar (B5 diff_sboms, B8 marketplace) wire edilir;
olmayanlar (B1 search, B4 CVE, B3 scheduler, B6 paralel, B2 tray, B7 web) yeni geliştirilir.
Python core'a eklenti modül(ler) eklenebilir; mevcut iş mantığı bozulmayacak.

## 2. Sidecar Method Sözleşmesi

### B1 — AUR Tarayıcı
| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| aur.search | {query, limit?} | [{name, version, description, num_votes, out_of_date, url_path}] | evet |
| aur.info | {name} | AurResult asdict | evet |
| aur.build | {name, install?} | {started} → event.aur_build_* | evet |

Yeni core: `search_aur(query, limit)` AUR RPC `/rpc/v5/search` ucunu kullanır.
`aur.build`: AUR git deposunu klonlar + makepkg (-si ile install opsiyonel).

### B4 — CVE Taraması
| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| security.cve_scan | {pkg_path} | {package, deps_scanned, vulns:[{id,summary,severity,affected_dep}], count} | evet |

Yeni core: `core/cve_scanner.py` — paket bağımlılıklarını (package_analyzer.depends)
OSV.dev API'sine (https://api.osv.dev/v1/query, anahtarsız) sorgular. Çevrimdışıysa
zarifçe {count:0, offline:true} döner.

### B5 — Paket Karşılaştırma
| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| compare.diff | {old_path, new_path} | SBOMDiff.to_dict() + boyut/bağımlılık özeti | evet |

Mevcut `diff_sboms(old,new)` kullanılır; her iki paket için SBOM üretilir.

### B3 — Zamanlanmış Görevler
| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| schedule.get | {} | {enabled, interval_hours, next_run, task} | hayır |
| schedule.set | {enabled, interval_hours?, task?} | {ok} | hayır |

Sidecar'da daemon scheduler thread: her dakika uyanır, ayarlanan aralığa göre
`task` (varsayılan "check_updates") çalıştırır, `event.schedule_ran` yayar.

### B6 — Toplu İşlem
| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| queue.add | {paths[]} | {added} | hayır |
| queue.list | {} | [{id, name, status, priority}] | hayır |
| queue.priority | {id, priority} | {ok} | hayır |
| queue.remove | {id} | {ok} | hayır |
| queue.start | {parallel?} | {started} | evet |
| queue.clear | {status?} | {ok} | hayır |

Paralel dönüştürme: `_pipeline` global yerine item-id → pipeline dict. Her pipeline
event'lerine `item_id` eklenir. Frontend kuyruğu id ile takip eder.

### B8 — Plugin Pazarı
| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| plugin.list | {} | list_installed_plugins() | hayır |
| plugin.available | {} | fetch_available_plugins() | evet |
| plugin.install | {name, version?, force?} | {ok, path} | evet |
| plugin.uninstall | {name} | {ok} | hayır |
| plugin.update | {name} | {ok, message} | evet |
| plugin.audit | {} | audit_plugins() | evet |

### B2 — Tray + Bildirim (Rust)
- `tauri-plugin-notification` eklenir (Cargo.toml + lib.rs).
- Tauri tray ikonu: Göster/Gizle, Dönüştür, Çıkış menüsü.
- Sidecar `event.finished` → Rust → bildirim (başarı/başarısız).

### B7 — Web/LAN API
| Komut | Açıklama |
|-------|----------|
| `pkgforge serve --http [--port N] [--token T]` | METHODS'ı HTTP JSON-RPC olarak LAN'a açar |

Python `http.server` tabanlı, bearer-token auth, CORS kapalı. Stdio sidecar'dan bağımsız
ayrı mod. Frontend desktop uygulaması değişmez; bu uzaktan yönetim temelidir.

## 3. Frontend Sayfaları

- **Browse** (sidebar aktif): AUR arama kutusu + sonuç tablosu (ad, versiyon, oy, açıklama)
  + satır aksiyonları (Bilgi, Derle).
- **Plugins** (sidebar aktif): Kurulu/Kullanılabilir sekmeleri, kur/kaldır/güncelle/denetle.
- **Compare** (yeni sidebar öğesi): iki paket seç → diff tablosu (eklenen/silinen dosyalar,
  boyut değişimi, bağımlılık farkı).
- **Security** genişletme: "CVE Tara" sekmesi.
- **Updates** genişletme: Zamanlayıcı kartı (B3).
- **Convert** genişletme: kuyruk öncelik/filtre/toplu aksiyonlar (B6).

## 4. Sidebar Değişiklikleri
- browse: aktif, plugins: aktif, YENİ compare (icon: GitCompare, "Karşılaştır").

## 5. Test Stratejisi
- Python: her yeni method için unit test (ağ bağımlı olanlar offline-mock).
- Frontend: her yeni sayfa için vitest (mock rpc).
- Regression: 656 Python + 45 vitest yeşil kalacak.

## 6. Uygulama Sırası
| # | Milestone | Kapsam |
|---|-----------|--------|
| F2.1 | B8 Plugins + B5 Compare | hazır kod wiring + sayfalar |
| F2.2 | B1 AUR Browse | search_aur + Browse sayfası |
| F2.3 | B4 CVE | cve_scanner.py + Security sekmesi |
| F2.4 | B3 Scheduler + B6 Toplu işlem | scheduler thread + queue refactor |
| F2.5 | B2 Tray + Bildirim | Rust tray + notification |
| F2.6 | B7 Web/LAN | serve --http modu |
| F2.7 | Entegrasyon + ROADMAP + push | full suite, E2E, tag |

## 7. Kısıtlar
- Mevcut token/design system; Türkçe UI; repo PRIVATE.
- Ağ gerektiren özellikler çevrimdışı zarif bozulur (hata fırlatmaz).
- Paralel dönüştürme item-id bazlı event routing ile yapılır.
