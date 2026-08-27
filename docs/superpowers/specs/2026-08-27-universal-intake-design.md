# Evrensel Girdi Katmanı — Universal Intake (Design Spec)

> Tarih: 2026-08-27 · Durum: ONAYLI (kullanıcı "Tavsiyeni planlayıp uygula")
> Bağlayıcı: docs/ROADMAP.md UI mimarisi (Tauri+React+sidecar) · 2026 UI/UX standartları
> Önceki değerlendirme: PyQt6 ve Tauri UI ikisi de sadece .deb/.rpm kabul ediyor.

## 1. Problem

PkgForge üç kapıda yalnızca `.deb`/`.rpm` kabul ediyor:
- `desktop/src/components/DropZone.tsx:5` → `ACCEPTED_EXTENSIONS=[".deb",".rpm"]`
- `core/api_server.py:126` → `if suffix not in (".deb",".rpm"): raise`
- `ui/drop_zone.py:25` → `_ACCEPTED_SUFFIXES={".deb",".rpm"}`

Oysa core'da hazır yetenekler var: AppImage→deb, Flatpak export, from-source
(cargo/cmake/meson/pyproject), rpm→deb. Kullanıcı `.tar.gz` bırakıp kuramıyor.
2026 standardı **intent-driven UX** bunu gerektirir: dosyayı bırak, uygulama anlasın.

## 2. Çözüm — Merkezi Yönlendirici (Approach A→C)

Yeni tek doğruluk kaynağı **`core/intake.py`**. UI-bağımsızdır; hem PyQt6 hem
Tauri/web sidecar aynı sınıflandırıcıyı kullanır. Mevcut dönüştürücüler DEĞİŞMEZ,
yeniden kullanılır.

### 2.1 Veri modeli

```python
class FileType(StrEnum):
    DEB; RPM; APPIMAGE; FLATPAKREF; SOURCE_TARBALL; BINARY_TARBALL
    ARCH_PKG; SOURCE_DIR; UNKNOWN

@dataclass
class IntakeResult:
    file_type: FileType
    path: Path
    confidence: float          # 0..1
    reason: str                # neden bu sınıflandırma (log/UI için)
    build_system: str | None   # SOURCE_TARBALL/SOURCE_DIR için: cargo/cmake/...
    ambiguous: bool            # True ise kullanıcıya sor
    actions: list[str]         # önerilen eylemler (Alt Proje 2 temeli)
```

### 2.2 Sınıflandırma — `classify(path) -> IntakeResult`

Üç aşama (ucuzdan pahalıya):
1. **Sonek** (hızlı yol): `.deb`,`.rpm`,`.AppImage`,`.flatpakref`,`.pkg.tar.zst/xz`
2. **Magic bytes** (uzantısız/yanıltıcı): DEB=`!<arch>`, RPM=`\xed\xab\xee\xdb`
3. **İçerik sezgisi** (tarball): arşivi **tam açmadan** `tarfile`/`zipfile` ile listele

### 2.3 `.tar.gz` kararı (Seçenek C — otomatik algıla, belirsizse sor)

| Arşiv içeriği | Sınıflandırma | Rota |
|---|---|---|
| `Cargo.toml`/`CMakeLists.txt`/`meson.build`/`pyproject.toml`/`setup.py`/`configure`/`Makefile`/`go.mod` | SOURCE_TARBALL | `from_source` → PKGBUILD → `makepkg` |
| `usr/bin/*`+`*.desktop` veya hazır binary yerleşimi | BINARY_TARBALL | yeni sarma işleyicisi → Arch paketi → kur |
| `.PKGINFO` (`.pkg.tar.*`) | ARCH_PKG | doğrudan `installer` |
| Hiçbiri / çelişkili | UNKNOWN (`ambiguous=True`) | **diyalog**: kaynak / binary / sadece aç |

### 2.4 Dispatch — her tür → mevcut işleyici

| FileType | İşleyici (mevcut) |
|---|---|
| DEB | `core.deb_converter` / `native_deb_converter` |
| RPM | `core.rpm_converter` |
| APPIMAGE | `core.appimage_converter.appimage_to_deb` |
| FLATPAKREF | `core.flatpak_converter` |
| SOURCE_TARBALL | geçici dizine aç → `core.from_source.generate_pkgbuild_from_source` → `makepkg` |
| SOURCE_DIR | doğrudan `core.from_source` |
| ARCH_PKG | `core.installer` (doğrudan kur) |
| BINARY_TARBALL | **yeni** `core/intake.py::wrap_binary_as_pkg` → `/opt`+`.desktop` → `makepkg` |
| UNKNOWN | hata veya belirsizlik diyaloğu |

## 3. Değişen dosyalar

| Dosya | Değişiklik |
|---|---|
| `core/intake.py` | YENİ — sınıflandırıcı + tarball sezgisi + dispatch registry + binary sarma |
| `core/pipeline.py` | `_run_pipeline` intake ile tür-bazlı dispatch; DEB/RPM yolu korunur |
| `core/api_server.py` | `handle_pipeline_start` sert filtreyi `intake.classify` ile değiştirir |
| `ui/drop_zone.py` | `_ACCEPTED_SUFFIXES` kaldırılır; tüm dosyalar pipeline'a |
| `desktop/src/components/DropZone.tsx` | `ACCEPTED_EXTENSIONS` genişletilir + filtre gevşetilir |
| `ui/ambig_dialog.py` | YENİ — belirsiz tarball için seçim diyaloğu (PyQt6) |
| i18n tr/en | yeni anahtarlar: intake.*, ambig.* |

## 4. Hata ele alma

- Bilinmeyen tür → net mesaj + desteklenen türler listesi
- Bozuk/okunamaz arşiv → nedenli hata (`tarfile.ReadError` yakalanır)
- Rota için araç eksik (makepkg/bsdtar yok) → `doctor` tarzı ipucu
- Belirsiz tarball → `ambiguous=True`, UI diyalog açar

## 5. Test stratejisi (%100 kapsama korunur)

- `classify()` her FileType için fixture (gerçek dpkg-deb/rpmbuild/tarfile ile üretilmiş)
- Tarball sezgisi: kaynak / binary / belirsiz / bozuk arşiv
- Magic-bytes: uzantısız DEB/RPM
- Dispatch: her türün doğru işleyiciye eşlenmesi
- `wrap_binary_as_pkg`: PKGBUILD üretimi + `.desktop`
- Belirsizlik diyaloğu (PyQt6 offscreen)
- Entegrasyon: `api_server.handle_pipeline_start` yeni türleri kabul eder

## 6. Kapsam dışı (bu alt projede YOK)

- Eylem modeli UI'ı (Alt Proje 2) — sadece `actions` alanı hazırlanır
- Komut paleti / design token (Alt Proje 3)
- Flatpak **kurulu uygulama** export UI (CLI var; GUI ayrı iş)

## 7. Başarı kriteri

Kullanıcı bir `.tar.gz` (kaynak veya binary) sürükleyip bırakır; PkgForge türü
otomatik algılar, belirsizse sorar ve Arch paketine çevirip kurar. Tüm mevcut
.deb/.rpm akışları aynen çalışır. Tam suit yeşil, kapsama %100.