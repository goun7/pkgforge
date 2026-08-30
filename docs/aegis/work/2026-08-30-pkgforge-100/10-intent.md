# Task Intent — PkgForge 100/100

## Goal
Kullanıcının raporladığı 3 somut hata + UI/UX derin taraması ile projeyi 100/100'e taşımak:
1. Binary tarball (Devin-linux-x64-3.8.20.tar.gz) paketleme hataları — dangling symlink, missing deps (cairo/glib2), unknown SPDX license, ELF in opt/.
2. UI EN iken TR hardcoded / TR iken EN hardcoded string kalıntıları — i18n temizliği.
3. Step-progress 2. adım yeşil tik bug'ı (MALWARE_SCAN enum index kayması).
4. Kurulum başarılı ama uygulama açılmıyor — wrapper + .desktop + ResultDialog "Aç" butonu.
5. Ek özellik taraması (UI/UX derinlemesine).

## Baseline
- git @ 89593b3 (all gates green: ruff, mypy 310 files, pytest 582+, bandit, vitest 582, tsc build OK)
- README/findings known inconsistencies documented.

## Impact
- core/intake.py (generate_binary_pkgbuild), core/pipeline.py (_wrap_binary, STEP_LABELS), ui/step_progress.py, ui/main_window.py, i18n/lang_tr.py, lang_en.py, ui/result_dialog.py
- Desktop (Tauri) i18n parity.

## Approach
AgentTeams: core-i18n (A1 binary packaging + A2 i18n core), ui-fixer (A3 step bug + A4 launch UX), qa-guard (A5 gates + regression). Captain: coordination + review + final commit.

## Stop
All 5 tasks completed; gates green; user-visible bugs verified fixed via tests.
