# PkgForge Tamamlama Planı (v2 — olay sonrası yeniden oluşturuldu)

> T1–T8 commit edildi (0e931b0..ad5a2cd). Kalan: T9–T15.
> NOT: 2026-09-04'te bash literal genişlemesiyle proje dizini silindi;
> GitHub'dan clone + konuşma replay'iyle T1–T8 kurtarıldı. Yedek: .git/pkgforge-work-backup.bundle + /tmp.

## T9 — CI dürüstlük
- .github/workflows/test.yml: --cov-fail-under=100 → 99 (tüm kopyalar), "78 gate" kaldır,
  permissions: contents: read + concurrency ekle, "Type Check (strict)" adını doğru koya,
  Windows job'da -o timeout_method=thread.
- workspace.toml coverage_required=99.
- .github/dependabot.yml oluştur (pip + npm + cargo).
- git rm QUALITY_100.md (100% iddiası yalan).

## T10 — Py3.10 uyumluluğu + api extra
- core/_toml.py shim (tomllib/tomli fallback), workspace.py:11 shim kullan.
- tests/test_toml_shim.py.
- pyproject: api = ["fastapi>=0.111.0", "uvicorn[standard]>=0.30.0", "pydantic>=2.7.0"] extra.
- cli.py: fastapi import'u graceful guard (ImportError → "pip install pkgforge[api]").
- api_v2.py APP_VERSION'ı config'ten al; requirements.txt yorumu; PKGBUILD optdepends.

## T11 — Paketleme doğruluğu
- scripts/uninstall.sh (helper policy, /usr/share/pkgforge/scripts, metainfo, delta unit'leri).
- git rm data/org.pkgforge.app.policy + pyproject data-files + install.sh referansları.
- install.sh tar excludes (tests/docs/.github/htmlcov) + kök config.py import'u yerine grep/sed sürüm okuma.
- install-packaging-tools.sh appimagetool pin + sha256.

## T12 — PyQt6 GUI
- ui/history_dialog.py:309-351 senkron pkexec → background worker (ui/background_worker.py imzasına bak).
- ui/tools_dialog.py:443-460 onay diyaloğu.
- ui/main_window.py closeEvent (768-786) + _on_cancel guard (288, 496-499) + fleet tooltip (738-743).
- Yeni i18n anahtarları (tr/en).

## T13 — Desktop (Tauri)
- tauri.conf.json CSP (null → gerçek policy).
- sidecar.rs: reader-end child.wait() + stdin=None + event.
- rpc_call respawn; lib.rs expect → eprintln.
- build-sidecar.sh → target/resources/pkgforge-sidecar; binary'yi git'ten çıkar + .gitignore.
- i18n sızıntıları (Tools.tsx, Convert.tsx, Dialog.tsx aria-label); documentElement.lang; ARIA tabs; dead branch.

## T14 — Repo hijyeni
- SECURITY.md gerçek kontakt (GitHub Private Vulnerability Reporting).
- İç dokümanları git'ten çıkar (MONETIZATION_PLAN, progress, findings, SECURITY_REVIEW, task_plan) + .gitignore.
- chmod 644 tracked non-executable'lar; ignored junk temizliği.

## T15 — Final ölçüm + hizalama
- Tam pytest+cov, collect sayısı, wheel, ruff/mypy/bandit, vitest/tsc/cargo.
- README badge'leri + RELEASE_READINESS + QUALITY_SUMMARY + CHANGELOG + docs/COVERAGE_GAPS gerçek ölçümle.
- docs/adr/004-api-and-plugin-disposition.md.
- Final kanıt raporu. PUSH YOK.

## Ertelendi (bilinçli)
- CLI package refactor, Qt removal from core, round-numbered test consolidation, mutmut expansion, actions SHA-pin.
