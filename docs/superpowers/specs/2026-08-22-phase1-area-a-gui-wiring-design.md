# Faz 1 — Alan A: Mevcut Özellikleri GUI'ye Taşı (Design Spec)

> Tarih: 2026-08-22 · Durum: ONAYLI (kullanıcı "Başla" ile Faz 1'i başlattı)
> Bağlayıcı: docs/ROADMAP.md A1–A6 maddeleri

## 1. Kapsam

47 core modülünün tümü mevcut. İş = bu modülleri sidecar'a JSON-RPC method'u olarak
bağlamak ve frontend sayfaları inşa etmek. Core'a YENİ iş mantığı eklenmeyecek;
sadece serileştirme köprüleri (dataclasses.asdict) ve thread sarmalayıcıları.

## 2. Sidecar Method Sözleşmesi

### 2.1 A1 — Export Merkezleri

| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| export.oci | {pkg_path, tag?} | {ok, message, output_path} | evet |
| export.appimage_to_deb | {appimage_path, output_dir?} | {ok, message, deb_path} | evet |
| export.flatpak_list | {} | [{app_id, name, version, branch}] | hayır |
| export.flatpak_to_deb | {app_id, branch?, output_dir?} | {ok, message, deb_path} | evet |

Event'ler: event.export_progress {step, pct}, event.export_log {line}, event.export_done {ok, message, path}

### 2.2 A2 — Güvenlik Paneli

| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| security.sign | {pkg_path, key_path?, passphrase?} | {ok, message} | evet |
| security.verify | {pkg_path} | SignatureInfo asdict | hayır |
| security.keys | {} | [{id, fingerprint, signer}] | hayır |
| security.sbom | {pkg_path, include_hashes?} | SBOMDocument.to_dict() | evet |
| security.quality | {pkg_path} | QualityReport asdict + passed | evet |
| security.provenance | {pkg_path} | BuildProvenance.to_dict() \| null | hayır |
| security.provenance_create | {source_file, output_file, source_type?, source_url?} | BuildProvenance.to_dict() | evet |
| security.sigstore_status | {} | dict | hayır |

### 2.3 A3 — Bağımlılık Grafiği

| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| graph.build | {pkg_path, files?} | {root, nodes, stats, mermaid} | evet |

nodes: {name: {version, deps[], needed_by[], is_installed, is_foreign}}
stats: {total, installed, missing, foreign, max_depth}

### 2.4 A4 — Delta Güncelleme

| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| delta.status | {} | get_auto_update_status() dict | hayır |
| delta.enable | {} | {ok, message, requires_privilege?} | hayır |
| delta.disable | {} | {ok, message, requires_privilege?} | hayır |

### 2.5 A5 — Kaynaktan PKGBUILD

| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| source.generate | {repo_url, output_dir?} | {ok, proj_name, build_system, pkgbuild_path, pkgbuild_content} | evet |

Event'ler: event.source_progress {step}, event.source_log {line}, event.source_done {ok, ...}

### 2.6 A6 — Sistem Araçları

| Method | Params | Result | Thread? |
|--------|--------|--------|---------|
| system.health | {} | {total, installed, converted, failed, success_rate, by_type, by_arch, url_count} | hayır |
| system.cross_check | {package_name, local_version?} | CrossCheckReport asdict | evet |
| system.snapshot_status | {} | get_cleanup_status() dict | hayır |
| system.snapshot_install | {max_age_days?} | {ok, message, requires_privilege?} | hayır |
| system.snapshot_remove | {} | {ok, message, requires_privilege?} | hayır |
| system.verify_rollback | {} | RollbackVerifyResult asdict | evet |
| system.benchmark | {quick?} | BenchmarkReport asdict + passed | evet |

Event'ler: event.bench_progress {name, pct}, event.bench_done {report}

## 3. Frontend Sayfaları

### 3.1 Security Sayfası (sidebar "security" aktif)
- Paket seçici (Tauri dosya diyaloğu, .pkg.tar.zst filtresi)
- Sekmeler: İmza | SBOM | Kalite | Provenance | Sigstore
- İmza sekmesi: doğrula butonu → SignatureInfo kartı; imzala butonu (passphrase input)
- SBOM sekmesi: özet kartı + dosya tablosu (path, type, size, sha256 kısaltılmış)
- Kalite sekmesi: puan göstergesi (total_score/max_score), grade badge, check listesi
- Provenance sekmesi: mevcut provenance görüntüle veya oluştur butonu
- Sigstore sekmesi: cosign durumu kartı

### 3.2 Updates Sayfası (sidebar "updates" aktif)
- Delta auto-update durum kartı: timer kurulu/aktif, sonraki çalışma
- Enable/Disable butonları (requires_privilege → toast)
- Cross-check bölümü: paket adı input → tablo (local, AUR, Flatpak versiyonları + öneri)

### 3.3 Reports Sayfası (sidebar "reports" aktif)
- Health dashboard: başarı oranı halka grafik (CSS), tür dağılımı bar'lar, mimari listesi
- Benchmark: "Çalıştır" butonu → ilerleme → sonuç tablosu (test, süre, bellek, durum)
- Snapshot temizlik: durum kartı + kur/kaldır butonları
- Rollback doğrulama: "Doğrula" butonu → sonuç kartı (backend, snapshot, dosya sayısı)

### 3.4 Export Sayfası (yeni sidebar öğesi)
- Üç kart yan yana:
  - AppImage → DEB: dosya seç + dönüştür butonu + ilerleme
  - Flatpak → DEB: uygulama listesi tablosu + seç + dönüştür
  - OCI Container: paket seç + tag input + build butonu + ilerleme
- Her kartta sonuç: çıktı dosya yolu + toast

### 3.5 Convert Sayfası Genişletmeleri
- Başarılı dönüşüm sonrası sonuç alanında:
  - "OCI olarak dışa aktar" butonu (export.oci çağrısı)
  - "Bağımlılık grafiği" butonu → graph.build → interaktif graf paneli
- Yeni "Kaynaktan" sekmesi: URL input → tespit → PKGBUILD önizleme → kaydet

### 3.6 Bağımlılık Grafiği Bileşeni (DepGraph.tsx)
- SVG tabanlı radyal/ağaç düzen (harici kütüphane yok, saf React + SVG)
- Düğümler: renk kodlu (installed=yeşil, missing=kırmızı, foreign=sarı)
- Kenarlar: deps ilişkileri
- Hover: detay tooltip
- Zoom/pan: basit wheel + drag

## 4. Sidebar Değişiklikleri

NAV_ITEMS güncelleme:
- security: soon kaldır → aktif
- updates: soon kaldır → aktif
- reports: soon kaldır → aktif
- YENİ: export (icon: PackageOpen, label: "Dışa Aktar")

PAGE_TITLES güncelleme:
- export: "Dışa Aktar"

## 5. Serileştirme Stratejisi

to_dict() OLMAYAN dataclass'lar için sidecar handler'larında:
```python
from dataclasses import asdict
result = asdict(report)
result["passed"] = report.passed  # property'ler asdict'e girmez
```

Core modüllere DOKUNULMAYACAK. Sadece api_server.py genişletilecek.

## 6. Yetki Modeli

pkexec gerektiren işlemler (delta.enable/disable, snapshot_install/remove):
- Şimdilik: {ok: false, requires_privilege: true, message: "..."}
- Faz 2'de: gerçek pkexec çağrısı (installer.py deseni)

## 7. Test Stratejisi

- Python: her yeni method için unit test (mock core fonksiyonlar)
- Frontend: her yeni sayfa için vitest (mock rpc call)
- Entegrasyon: sidecar subprocess ile gerçek method çağrıları
- Mevcut 637 Python + 26 vitest testi regression olarak çalışacak

## 8. Uygulama Sırası (Milestone'lar)

| # | Milestone | Kapsam |
|---|-----------|--------|
| F1.1 | Sidecar A2+A4 methods | security.*, delta.* handler'ları + testler |
| F1.2 | Sidecar A1+A3+A5+A6 methods | export.*, graph.*, source.*, system.* + testler |
| F1.3 | Frontend Security + Updates sayfaları | sidebar aktif, sayfalar, vitest |
| F1.4 | Frontend Reports + Export sayfaları | sidebar aktif, sayfalar, vitest |
| F1.5 | Convert genişletmeleri + DepGraph | OCI butonu, graf bileşeni, Kaynaktan sekmesi |
| F1.6 | Entegrasyon + paketleme | E2E, full suite, commit, push |

## 9. Kısıtlar

- Python core'a yeni iş mantığı EKLENMEYECEK
- Harici frontend kütüphanesi eklenmeyecek (graf = saf SVG)
- Mevcut token/design system kullanılacak
- Türkçe UI metinleri (i18n hazır)
- Repo PRIVATE kalacak
