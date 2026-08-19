# PkgForge API Reference

## CLI Commands

### `pkgforge convert <file_or_url> [OPTIONS]`

Dönüştürme ve kurulum Ana akışı. DEB/RPM dosyasını veya URL'yi Arch Linux uyumlu `.pkg.tar.zst` paketine dönüştürür.

**Parametreler:**
| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `target` | `str` | Evet | `.deb`/`.rpm` dosya yolu veya `http://`/`https://` URL'si |
| `-i, --install` | `bool` | Hayır | Dönüşümden sonra otomatik kur (`pacman -U`) |
| `-y, --yes` | `bool` | Hayır | Kurulum onay istemini atla |
| `--dry-run` | `bool` | Hayır | Yalnızca dönüştür ve analiz et |
| `-o, --output-dir` | `str` | Hayır | Çıktı dizini (varsayılan: dosyanın bulunduğu dizin) |
| `--to-oci` | `bool` | Hayır | OCI konteyner görüntüsü oluştur (buildah/podman) |
| `--oci-tag` | `str` | Hayır | OCI görüntü etiketi |
| `--delta` | `bool` | Hayır | xdelta3 ile binary delta indirme |
| `--verify-build` | `bool` | Hayır | Reproducible build doğrulaması |
| `--sign` | `bool` | Hayır | Dönüşüm sonrası otomatik GPG imzası |
| `--sign-key` | `str` | Hayır | GPG anahtar dosyası yolu |

**İstisnalar:**
- `FileNotFoundError`: Hedef dosya/URL bulunamadığında
- `ValueError`: MIME type doğrulama başarısız olduğunda (zip bomb, traversal)
- `RuntimeError`: Converter Provider üretilemediğinde

**Örnek:**
```bash
pkgforge convert google-chrome.deb --install --yes
pkgforge convert https://example.com/app.rpm --to-oci --sign
pkgforge convert app.deb --delta --verify-build
```

---

### `pkgforge list`

Dönüşüm ve kurulum geçmişini listeler.

**Parametre:** Yok.

**Çıktı:** Tablo formatında: ID, Tarih, Paket Adı, Tür, Durum, Orijinal Dosya.

---

### `pkgforge remove <package>`

Kurulmuş bir paketi sistemden kaldırır (`pacman -R`).

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `package` | `str` | Evet | Geçerli pacman paket adı |

**Kısıtlama:** Paket adı `is_valid_package_name()` ile doğrulanır. Geçersiz karakterler reddedilir.

---

### `pkgforge rollback <package>`

Paketi önceki yedek sürümüne geri döndürür (`pacman -U`).

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `package` | `str` | Evet | Geri döndürülecek paket adı |

**Ön koşul:** Paket için kayıtlı yedek olmalı (`HistoryDB.backup_pkg`).

---

### `pkgforge check-updates`

Kayıtlı URL indirmelerinin güncellemelerini kontrol eder.

ETag/Last-Modified header'larını kullanarak upstream değişiklikleri tespit eder.

---

### `pkgforge rpm-to-deb <rpm-file> [-o output-dir]`

RPM paketini DEB formatına dönüştürür.

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `rpm` | `str` | Evet | `.rpm` dosya yolu |
| `-o, --output-dir` | `str` | Hayır | Çıktı dizini |

**Ön koşul:** `rpm2cpio` (rpmextract) ve `dpkg-deb` (dpkg) kurulu olmalı.

---

### `pkgforge flatpak-export <app-id> [--list]`

Flatpak uygulamasını DEB paketine dönüştürür.

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `app_id` | `str` | Evet* | Flatpak app ID (örn: `org.mozilla.firefox`) |
| `--list` | `bool` | Hayır | Yüklü Flatpak uygulamalarını listele |
| `--branch` | `str` | Hayır | Flatpak dalı (varsayılan: `stable`) |

*`--list` verilmezse zorunludur.

---

### `pkgforge appimage-export <file>`

AppImage dosyasını DEB paketine dönüştürür.

**Ön koşul:** `unsquashfs` (squashfs-tools) kurulu olmalı.

---

### `pkgforge graph <package> [OPTIONS]`

Paketin bağımlılık grafiğini gösterir.

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `package` | `str` | Evet | Paket adı veya .pkg.tar.zst dosya yolu |
| `--files` | `bool` | Hayır | Dosya tabanlı (shared library) grafik |
| `--format` | `ascii\|mermaid` | Hayır | Çıktı biçimi (varsayılan: ascii) |

**Not:** Paket kurulu olmalı veya `.pkg.tar.zst` dosyası mevcut olmalı.

---

### `pkgforge audit [--from YYYY-MM-DD] [--to YYYY-MM-DD]`

Denetim kaydını gösterir. Bütünlük kontrolü, anomali tespiti ve provenance doğrulama içerir.

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `--from` | `str` | Hayır | Başlangıç tarihi |
| `--to` | `str` | Hayır | Bitiş tarihi |

**İçerik:**
- Durum dağılımı ve tür istatistikleri
- Bütünlük kontrolü (çıktı/yedek dosya mevcudiyeti)
- Anomali tespiti (tekrarlayan paketler, başarısız ama yeniden denenmemiş paketler)
- Provenance kaydı doğrulama

---

### `pkgforge scan-image <image>`

OCI konteyner görüntüsünü güvenlik tarar.

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `image` | `str` | Evet | `.tar`, `.oci` veya dizin yolu |

**Tarama araçları (otomatik algılama):**
- `trivy image` → CVE taraması (HIGH/CRITICAL)
- `grype` → Bağımlılık açığı taraması
- `clamscan` → Malware taraması

**Timeout:** Her araç için 600 saniye.

---

### `pkgforge abi-check <package>`

ABI uyumluluğunu kontrol eder — GLIBC/GLIBCXX sembol sürümleri taraması.

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `package` | `str` | Evet | `.pkg.tar.zst` dosya yolu |

**Tespit edilen sorunlar:**
- GLIBC sembol sürüm uyumsuzluğu (örn: `GLIBC_2.33` gerekli ama `GLIBC_2.31` mevcut)
- Eksik paylaşılan kütüphaneler
- ELF dosyası tarama hataları

---

### `pkgforge health`

PkgForge sağlık durumunu ve istatistiklerini gösterir.

**Çıktı:** Başarı oranı, tür dağılımı, son aktivite, başarısız paketler, sağlık skoru.

---

### `pkgforge from-source <git-url> [-o output-dir]`

Kaynak koddan PKGBUILD oluşturur.

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `repo_url` | `str` | Evet | Git depo URL'si |
| `-o, --output-dir` | `str` | Hayır | PKGBUILD çıktı dizini |

**Otomatik tespit:**
- Build sistemi: cmake, meson, cargo, autotools, make, python, node
- Versiyon: Cargo.toml, CMakeLists.txt, meson.build, pyproject.toml, VERSION dosyası
- Lisans: LICENSE/COPYING dosyaları, Cargo.toml, package.json

---

### `pkgforge benchmark [--bench-file file] [--quick]`

Performans ölçümü yapar.

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `--bench-file` | `str` | Hayır | Ölçüm yapılacak .deb/.rpm dosyası |
| `--quick` | `bool` | Hayır | Hızlı mod (ağır testleri atlar) |

**Ölçülen metrikler:**
- Test DEB oluşturma süresi
- SHA-256 hash hızı
- MIME doğrulama hızı
- Paket analiz hızı
- Güvenlik kontrolü hızı
- xdelta3 delta oluşturma hızı

---

### `pkgforge sign <package> [--key key]`

Paketi GPG ile imzalar.

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `package` | `str` | Evet | `.pkg.tar.zst` dosya yolu |
| `--key` | `str` | Hayır | GPG anahtar dosyası (varsayılan: default key) |

---

### `pkgforge verify <package>`

Paketin GPG imzasını doğrular.

---

### `pkgforge provenance <package>`

Paketin SLSA provenance kaydını doğrular.

---

## Core Modules

### `core/package_analyzer.py`

```python
from core.package_analyzer import analyze_package
from config import discover_tools

tools = discover_tools()
meta = analyze_package(Path("package.deb"), tools)

# meta.name        — str: Paket adı
# meta.version     — str: Paket sürümü
# meta.arch_mapped — str: Eşleştirilmiş mimari ("x86_64", "any", "i686", "aarch64")
# meta.file_list   — list[str]: Paket içindeki dosyalar
# meta.depends     — list[str]: Bağımlılıklar (isim-only)
# meta.package_type — str: "deb" veya "rpm"
# meta.file_path   — Path: Orijinal dosya yolu
```

**İstisnalar:**
- `ValueError`: Dosya bulunamadığında veya MIME type geçersiz olduğunda
- `subprocess.TimeoutExpired`: ar/tar işlemi zaman aşımında

---

### `core/security.py`

```python
from core.security import (
    validate_mime_type,      # (Path, ToolPaths) -> str | raises ValueError
    validate_file_size,      # (Path, int, int) -> None | raises ValueError
    sha256_hash,             # (Path) -> str (64 hex karakter)
    check_path_traversal,    # (list[str]) -> list[str] (ihlal eden yollar)
    check_compression_bomb,  # (Path, ToolPaths) -> str | None (uyarı)
    safe_run,                # (list[str], **kwargs) -> CompletedProcess
    is_valid_package_name,   # (str) -> bool
)
```

**`validate_mime_type(path, tools)`:**
- Geçerli MIME'lar: `application/x-debian-package`, `application/x-rpm`, `application/x-tar`, `application/gzip`, `application/x-xz`
- Hata: `ValueError(mesaj)` — MIME type tanınamıyorsa veya zip bomb tespit edildiyse

**`validate_file_size(path, min_bytes, max_mb)`:**
- `min_bytes`: Minimum dosya boyutu (bayt)
- `max_mb`: Maksimum boyut (MB)
- Hata: `ValueError(mesaj)` — boyut kısıtlamalara uymuyorsa

**`safe_run(cmd, **kwargs)`:**
- `shell=True` KULLANMAZ — her zaman list olarak çalıştırır
- Varsayılan `timeout=120`
- `check=False` varsayılan (hata durumunda Raise etmez)

**`check_compression_bomb(path, tools)`:**
- `file --mime-type` ve sıkıştırma oranı kontrolü
- Döner: `str` (uyarı mesajı) veya `None` (temiz)

---

### `core/provenance.py`

```python
from core.provenance import create_provenance, save_provenance, load_provenance, verify_provenance

prov = create_provenance(
    source_file=Path("input.deb"),       # Path veya str
    source_url="https://...",            # str (opsiyonel)
    source_sha256="a1b2...",            # str (opsiyonel)
    output_file=Path("output.pkg"),     # Path veya str (opsiyonel)
    output_sha256="c3d4...",            # str (opsiyonel)
    tools=discover_tools(),             # ToolPaths (opsiyonel)
    package_name="myapp",               # str (opsiyonel)
    package_type="deb",                 # str (opsiyonel)
)
# prov.build_id       — str: "build-{timestamp}-{random}"
# prov.provenance_hash — str: SHA-256 (self-referential)
# prov.build_timestamp — str: ISO 8601

valid, msg = verify_provenance(prov)
# valid: bool
# msg: str — "Doğrulama başarılı" veya hata açıklaması
```

---

### `core/dep_graph.py`

```python
from core.dep_graph import build_dep_graph, build_file_dep_graph

# Paket-seviye grafik (pacman bağımlılıkları)
graph = build_dep_graph(Path("/var/cache/pacman/pkg/app-1.0.pkg.tar.zst"))
# graph.nodes  — dict[str, DepNode]
# graph.root   — str (paket adı)
# graph.warnings — list[str] (uyarı mesajları)

print(graph.to_ascii())     # ASCII ağacı
print(graph.to_mermaid())   # Mermaid flowchart
stats = graph.stats()        # {total, installed, missing, foreign, max_depth}

# Dosya-seviye grafik (shared library)
graph = build_file_dep_graph(Path("app-1.0.pkg.tar.zst"))
# ELF dosyaları file(1) ile algılanır
# ldd ile shared library bağımlılıkları haritalanır
```

**Uyarılar:**
- Paket kurulu değilse `graph.warnings` dolu olur
- ELF dosyası bulunamazsa uyarı eklenir
- ldd çalışmıyorsa uyarı eklenir

---

### `core/abi_scanner.py`

```python
from core.abi_scanner import scan_elf_symbols, check_abi_compatibility

# Tek ELF dosyası tarama
mismatches = scan_elf_symbols(Path("/usr/bin/myapp"))
# mismatches: list[SymbolMismatch]
# Her item: binary, symbol, required_version, available_version, library, severity

# Tüm paket tarama
report = check_abi_compatibility(Path("myapp.pkg.tar.zst"))
# report.binary_count    — int: Taranan ELF dosyası sayısı
# report.mismatches      — list[SymbolMismatch]: Sembol uyumsuzlukları
# report.missing_libs    — list[tuple[str, str]]: (binary, kütüphane)
# report.passed          — bool: Tüm uyumluluk sağlam
# report.summary()       — str: Formatlı rapor
```

**Kullanım Notları:**
- `readelf` gerekli (binutils paketi)
- Sadece GLIBC/GLIBCXX sürümlerini kontrol eder
- Host sistemi ile karşılaştırma yapar

---

### `core/from_source.py`

```python
from core.from_source import generate_pkgbuild_from_source

pkgbuild = generate_pkgbuild_from_source(
    name="myproject",                    # str: Proje adı
    repo_url="https://github.com/...",  # str: Git URL
    build_system="cmake",               # str: cmake|meson|cargo|autotools|make|python|node
    repo_dir=Path("/tmp/repo"),          # Path: Klonlanmış depo dizini
)
# pkgbuild: str — Tam PKGBUILD içeriği
```

**Otomatik Tespit:**
- Versiyon: `Cargo.toml`, `CMakeLists.txt`, `meson.build`, `pyproject.toml`, `VERSION`
- Lisans: `LICENSE`/`COPYING` dosyası içerik taraması (12+ SPDX ID)
- Binary adı: `Cargo.toml` `[[bin]]`, `CMakeLists.txt` `add_executable()`, `package.json` `bin`

---

### `core/benchmark.py`

```python
from core.benchmark import run_benchmarks

report = run_benchmarks(
    test_file=Path("test.deb"),  # Path | None: Özel test dosyası
    quick=False,                  # bool: Hızlı mod
)
# report.results    — list[BenchmarkResult]
# report.total_duration_ms — int
# report.passed     — bool
# report.summary()  — str: Formatlı tablo
```

---

### `core/package_signing.py`

```python
from core.package_signing import sign_package, verify_signature

ok, msg = sign_package(
    pkg_path=Path("package.pkg.tar.zst"),
    key_path=None,  # Path | None: Varsayılan key kullanılır
)
# ok: bool, msg: str

info = verify_signature(Path("package.pkg.tar.zst"))
# info.valid            — bool
# info.signer           — str: İmza sahibi
# info.key_id           — str: Key ID
# info.key_fingerprint  — str: Fingerprint
# info.detail           — str: Detaylı açıklama
```

**Ön koşul:** `gpg` kurulu olmalı.

---

### `core/cli_bridge.py`

PyQt6 event loop olmadan senkron dönüşüm sağlar. CLI modu için tasarlanmıştır.

```python
from core.cli_bridge import convert_deb_sync, convert_rpm_sync

result = convert_deb_sync(
    deb_path=Path("app.deb"),
    output_dir=Path("/output"),
    tools=discover_tools(),
    progress_callback=lambda line: print(line),  # callable | None
)
# result.success    — bool
# result.message    — str
# result.output_pkg — str (çıktı .pkg.tar.zst yolu)
```

**Not:** `threading.Event` kullanır, `QEventLoop` kullanmaz. PyQt6 bağımlılığı yoktur.

---

### `core/malware_scanner.py`

```python
from core.malware_scanner import scan_with_clamav, is_clamav_available, check_db_freshness

if is_clamav_available():
    ok, msg = scan_with_clamav(Path("package.deb"))
    # ok: bool, msg: str

    fresh = check_db_freshness()
    # fresh: bool — True ise veritabanı güncel
```

**Timeout:** 120 saniye (büyük dosyalar için yetersiz olabilir).

---

### `core/snapshot_manager.py`

```python
from core.snapshot_manager import SnapshotManager, detect_backend

backend = detect_backend()
# backend: "btrfs" | "zfs" | "none"

if backend != "none":
    mgr = SnapshotManager(backend)
    snap_id = mgr.create_snapshot("before-install")
    # snap_id: str

    ok = mgr.rollback(snap_id)
    # ok: bool
```

**Not:** Root filesystem geri yükleme sadece Btrfs/ZFS ile çalışır.
