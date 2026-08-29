# PkgForge — Faz 12: Hata/Bug Taraması ve Sızıntı Düzeltmeleri

> **Amaç:** Statik kapılar (ruff/mypy/bandit/tsc) zaten yeşil olduktan sonra
> gerçek hata sınıflarını (yarış koşulları, kaynak sızıntıları, ölümkilitler)
> kod okuyarak taramak ve doğrulanmış bulguları düzeltmek.

## Tarama Yöntemi
Statik analiz kapıları ilk turda doğrulandı (ruff 0 / mypy 0/77 / bandit 0
High-Medium). Ardından iki yüzeyde desen taraması + satır satır okuma:
- Python: Popen boruları, time.sleep, bare-pass blokları (43), TODO artıkları (0).
- Desktop TS: catch blokları (122), .then desenleri (36), index-key (8),
  timer/interval cleanup (13), any-cast (yalnız testlerde).

## Doğrulanmış Bulgular ve Düzeltmeler

### 12.1 Python — ar/tar borusunda stderr ölümkilidi (ORTA) — DÜZELTİLDİ
`core/subprocess_converters.py` `_extract_data_tar`: `ar_proc.stderr`
hiç okunmuyordu. ar stderr çıktısı 64KB boru tamponunu doldurursa ar blokla-
nır; tar da ar'ın stdout'unu beklediğinden ikisi kilitlenir ve 60s timeout'a
dek asılı kalır. `native_deb_converter.py`'de aynı hata daha önce düzeltilmişti
bu kopyada düzelmemişti (klasik kopya-yapıştır sapması). Ayrıca ar/tar
returncode hiç kontrol edilmiyordu — sessiz bozuk çıkarım. Parite deseni
uygulandı: stderr paralel okuma + `wait(30)` + iki returncode kontrolü.
Testler: `test_deb_extract_data_tar_ar_and_tar_failures` (2 yeni hata-yolu
testi) + fake'e eksik `wait` eklendi.

### 12.2 Desktop — abonelik unmount yarışı (ORTA, 33 nokta) — DÜZELTİLDİ
`onEvent(...).then((u) => unsubs.push(u))` deseni: useEffect cleanup'u
`listen()` promise'i çözülmeden tetiklenirse (tembel sayfa değişimi) abonelik
geri alınamaz — kalıcı sızıntı. `rpc.ts`'ye `eventBinder()` eklendi: çözülmemiş
abonelikleri de izler, dispose'dan sonra çözülen anında kendini kaldırır.
10 sayfa migrate edildi (Browse/Tools/Fleet/Compare/Plugins/Reports/Settings/
Convert/Security/Updates). 4 yeni birim test (`rpc.test.ts`).

### 12.3 Desktop — handler catch'inde abonelik sızması (ORTA, 6 nokta) — DÜZELTİLDİ
Export (×3), Security (×3), Updates, Reports (×2): `await onEvent(...)` ile
kurulan tek-seferlik abonelik RPC başarısız olursa `un()` çağrılmadan
bırakılıyordu. Catch bloklarına `un()` eklendi.

### 12.4 Desktop — Browse effect churn (DÜŞÜK) — DÜZELTİLDİ (bulgu 12.2 sayesinde)
Browse abonelik effect'inin bağımlılığı `[toast, t]`: `t = tFor(lang)` her
render'da yeni kimlik üretir → her state değişiminde (arama, sonuç, tooltip)
4 abonelik kopup yeniden kuruluyordu. Deps `[toast, lang]` yapıldı; `t` closure
içinde türetildi.

### 12.5 Yaralanma temizliği (kod değişikliği yok)
- `from_source.py` bare-pass'leri (11): docstring'ler açıkça best-effort
  ("asla raise etmez") — kasıtlı, değişmedi.
- `api_server.py:593` xdg-open Popen: kasıtlı fire-and-forget (DEVNULL) —
  değişmedi.
- `cloud_sync.py:70` sqlite sızıntısı ve polkit policy kurulumu: önceki fazlarda
  zaten düzeltilmiş (closing() deseni; install.sh:80-85).
- PKG-003/004/005, BUG-002/003: hepsi kapalı (CI akışı, systemd birimi,
  bytes decode, _ensure_qt_app kaldırılmış).

## Ölçüm: Masaüstü Kapsamı Güncellendi
Önceki oturumun test-kapsam maratonu (200+ yeni test) Faz 11 ölçümünden sonra
geldi; yeni ölçüm: **v8 ifade kapsamı %88.37** (satır %89.53), en düşük sayfa
Settings (%62.98). README rozetleri gerçek sayılara çekildi: 2409 toplanan
pytest testi / 528 vitest testi.

## Doğrulama
- `pytest tests/ -q` → rc=0 (tüm paket; **2409 toplanan** test).
- `ruff check .` / `mypy core/...` / `bandit -r core/ -ll` → temiz.
- `pnpm exec vitest run` → **44 dosya / 528 test hepsi geçti** (4 yeni
  eventBinder testi dahil); `tsc --noEmit` → 0 hata.
- Hedefli: `pytest tests/test_subprocess_converters_sweep.py` + converters → 26 geçti.
