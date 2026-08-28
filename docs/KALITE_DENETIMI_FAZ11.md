# PkgForge — Faz 11: Kapsamlı Kalite Denetimi ve Sertleştirme

> **Amaç:** Projeyi her açıdan (kod kalitesi, test, güvenlik, erişilebilirlik,
> performans, i18n, dokümantasyon, CI) 100/100'e ulaştırmak. Faz 7-10 UI/UX
> önerilerini tamamladı; Faz 11 statik analiz, güvenlik, CI tutarlılığı ve test
> kapsamı üzerinde sistematik bir denetim yapar.

## Denetim Sonuçları (tek bakışta)

| Alan | Araç | Durum |
|---|---|---|
| Python lint | `ruff check .` (0.16.4, tam repo) | ✅ 0 hata (6 hata düzeltildi) |
| Python tip | `mypy core/ --ignore-missing-imports` | ✅ 0 hata |
| Python güvenlik | `bandit -r core/ -ll` | ✅ 0 high / 0 medium |
| Python kapsam | `pytest --cov=core --cov=ui --cov=i18n` | ✅ %100 (11704 ifade) |
| TS tip | `tsc -b` (strict, noUnusedLocals/Params) | ✅ 0 hata, 0 `any` |
| Bağımlılık güvenliği | `pnpm audit` | ✅ 0 açık |
| Rust lint | `cargo clippy --all-features` | ✅ 0 uyarı |
| i18n tr/en tutarlılık | vitest `i18n.test.ts` | ✅ anahtar kümeleri özdeş |
| API tip aynası | `tools/gen_api_ts.py --check` | ✅ güncel (yeniden üretildi) |
| Masaüstü kapsam | `vitest --coverage` (v8) | ✅ %53 → **%72.63** (326 test) |

## 11.1 Ruff lint ihlalleri (CI kırıcıydı) — DÜZELTİLDİ
CI'ın `lint-hardened` işi `ruff check .`'i sert kapı olarak çalıştırır. 6 ihlal
tespit ve tamir edildi:
- `TRY004` `core/api_server.py` `handle_history_restore`: geçersiz tip için
  `ValueError` → `TypeError` (test de güncellendi).
- `RUF012` ×3: `tests/test_api_tools2_round63.py`, `tests/test_tools_dialog2_round63.py`
  içindeki `_FakeAtt` sınıflarının değişken sınıf özniteliklerine `ClassVar` eklendi.
- `PIE807` `tests/test_fleet_round64.py`: `lambda: {}` → `dict`.
- `F401` ×2: kullanılmayan `pathlib.Path` importları kaldırıldı.

## 11.2 API tip aynası bayattı (CI kırıcıydı) — YENİDEN ÜRETİLDİ
Faz 9'da eklenen `history.restore` RPC yöntemi `desktop/src/lib/api-types.ts`
aynasına yansımamıştı. CI'ın `gen_api_ts.py --check` adımı bunu yakalardı.
`python tools/gen_api_ts.py` ile ayna yeniden üretildi; `--check` artık geçiyor.

## 11.3 ESLint — EKOSİSTEM BOŞLUĞU (bilinçli erteleme)
Desktop için ESLint (typescript-eslint) kurulmaya çalışıldı. Ancak proje bilinçli
olarak **TypeScript ^7.0.2** (Go tabanlı yeniden yazım) kullanıyor ve
`typescript-eslint` (8.68) henüz TS 7'yi desteklemiyor — parser sürüm kapısında
sert hata veriyor. Sırf linter için TS'yi 6.x'e düşürmek projenin bilinçli seçimini
geri almak olacağından **kabul edilmedi**; ESLint temizce geri alındı
(`package.json`/`pnpm-lock.yaml` sıfır net değişiklik). TS 7 desteği geldiğinde
(`typescript-eslint` issue #10940) ESLint yeniden eklenecek.
Mevcut güçlü kapılar (tsc strict + 166 vitest + ruff + mypy + bandit) bu boşluğu
büyük ölçüde kapatır.

## 11.4 Masaüstü test kapsamı ölçümü ve iyileştirme — %53 → %72.63
`@vitest/coverage-v8` eklendi; `pnpm test:cov` script'i tanımlandı. İlk ölçümde
masaüstü kapsamı **%53.33 ifade** bulundu (Python %100 iken en büyük boşluk).
Tip-only `src/lib/types.ts` kapsamdan hariç tutuldu (çalışan kod içermez).
En düşük kapsamlı 6 sayfa (Security, Reports, Plugins, Export, Updates, Convert)
için **paralel 6 subagent** ile etkileşim/dal testleri eklendi: **+160 yeni test**
(toplam 166 → 326). Sonuç: **%72.63 ifade / %75.42 satır**.
- Coverage enstrümantasyonu render'ları yavaşlattığı için `testTimeout`/`hookTimeout`
  30000ms'e çıkarıldı (dar timeout flaky üretiyordu).

## 11.6 Event kontrat testi yanlış pozitifi — DÜZELTİLDİ
`tests/test_event_contract.py` `desktop/src` altında `__tests__` dosyalarını da
tarıyor, test mock/hata mesajlarındaki `"event/..." ` string'lerini üretim
dinleyicisi sanıyordu. Test dosyaları üretim frontend'i olmadığından tarama
kapsamından çıkarıldı; kontrat artık yalnız üretim kodunu denetliyor.

## 11.5 Dokümantasyon — GÜNCELLENDİ
- README test rozeti: `2147` → `2408 collected` (gerçek toplanan sayı).
- Yeni rozetler: masaüstü `166 vitest tests`, `ruff 0 errors`.
- "Key Features" bölümüne **Native Tauri Desktop App** maddesi eklendi
  (Tauri 2 + React 19, tr/en i18n, komut paleti, özellik turu, tembel sayfalar).

## Doğrulama
- `ruff check .` → All checks passed.
- `mypy core/` → 0 hata; `bandit -r core/ -ll` → 0 high/medium.
- `pytest --cov=core --cov=ui --cov=i18n` → **%100** (11704 ifade), 2408 test.
- `cargo clippy --all-features` → 0 uyarı.
- `tsc -b` → temiz; `pnpm test` → **326/326**; `pnpm build` → başarılı.
- `pnpm test:cov` → masaüstü **%72.63** ifade.
- `pnpm install --frozen-lockfile --dry-run` → lockfile güncel (CI uyumlu).
