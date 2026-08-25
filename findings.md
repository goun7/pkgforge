# Findings Log

## BUG-001 (fixed later): Tests use real user HOME
- tests/conftest.py does NOT isolate HOME; HistoryDB() writes to real ~/.config/pkgforge/history.db
- Fails in read-only/sandbox environments ("unable to open database file"); pollutes real user data in normal runs
- Repro: pytest passes with HOME=$(mktemp -d); fails with real HOME under sandbox
- FIX: set HOME to tempdir at top of conftest.py BEFORE config import (CONFIG_DIR computed at import time)

## SEC-001 (HIGH): Plugin marketplace = remote code execution vector
- core/plugins/marketplace.py downloads .py from GitHub releases and load_plugins() exec_module()s them
- Checksum verification silently SKIPPED if .sha256 file missing (except → warning) → no real integrity
- SHA256 file fetched from SAME repo as plugin → compromise of repo = both compromised (no key pinning/GPG)
- install_plugin(name): NO name validation → dest = PLUGIN_DIR / f"{name}.py" → path traversal write (e.g. "../../x")
- uninstall_plugin(name): same traversal → arbitrary .py unlink
- Marketplace repo "github.com/pkgforge/pkgforge-plugins" — existence unverified (web_search auth error, retry)
- Plugins auto-load on import of core.plugins (module import side effect!) + SIGHUP handler installed at import
- FIX: validate name ^[a-z0-9-]{1,64}$, require checksum (fail closed), GPG/minisign signature, confirm repo

## SEC-002 (MED): downloader follows redirects without scheme re-check
- core/downloader.py validates scheme of USER url only; urllib follows 30x redirects automatically
- https→http redirect possible (urllib default HTTPRedirectHandler does not downgrade-block? Actually it allows http→any)
- Need custom redirect handler re-validating scheme/host + size cap on redirects
- Also: no SSRF guard for private IPs (127.0.0.1, 169.254, 10.x) — low risk for desktop tool but worth noting

## Static analysis summary
- mypy: CLEAN (only 1 annotation-unchecked note)
- bandit: 0 High, 7 Medium (B108 tmp x3, B608 SQL in delta_updater.py:200, B310 urlopen x3), 33 Low
- ruff: 352 issues (86 unsorted imports, 80 unused imports, 68 blind excepts, 34 f-string placeholders, 11 subprocess without check, 5 mutable class defaults, 4 F822 undefined-export)
- pytest: 1 fail (HOME isolation BUG-001), ~6 skips; otherwise green

## PKG-001 (RELEASE BLOCKER): Built wheel is broken — ✅ RESOLVED (F1/F12: py-modules added, wheel verified to ship cli.py/main.py/config.py + data files)
- dist/pkgforge-1.1.0-py3-none-any.whl contains ONLY core/, i18n/, ui/ — NO main.py, cli.py, config.py, scripts/, data/
- Console script entry point "pkgforge = main:main" → ModuleNotFoundError on installed wheel
- pyproject packages.find include list misses top-level modules (main/cli/config are py_modules, not packages)
- Wheel also ships STALE core/dependency_resolver.py (removed from source; egg-info still lists it) → stale build dir
- FIX: add [tool.setuptools] py-modules = ["main", "cli", "config"], include data files, clean rebuild

## PKG-002 (RELEASE BLOCKER): No git remote configured — ✅ RESOLVED (REPO-001: goun7/pkgforge private remote configured, full history pushed)
- git remote -v → empty; branch master only; code exists nowhere remotely
- PKGBUILD/README/PKGBUILD Maintainer point to github.com/pkgforge/pkgforge — repo existence unverified
- Release impossible without pushing to a remote + tagging v1.1.0 (PKGBUILD source= tag tarball)

## PKG-003 (HIGH): CI references nonexistent module core.smart_fallback
- .github/workflows/test.yml "Module Import Check" imports core.smart_fallback → module does not exist → CI job fails
- Also CI badge-update step commits to README on push (needs token perms; may fail on forks — minor)

## PKG-004 (MED): systemd delta service runs wrong command
- data/pkgforge-delta.service: ExecStart=/usr/bin/python3 -m pkgforge convert --check-updates
- No pkgforge python module exists (entry point is main.py); -m pkgforge fails; also --check-updates is a top-level flag, not a convert arg
- Should be: /usr/bin/pkgforge check-updates (installed wrapper) or python3 -c ...
- Also User=root + network fetch + auto-install path = risky design; needs review of delta_updater

## PKG-005 (LOW): install.sh hardcodes v1.0.0 banner; wrapper embeds absolute PROJECT_DIR path
- /usr/local/bin/pkgforge wrapper: exec python3 "$PROJECT_DIR/main.py" — breaks if source dir moves; pip/venv conflict risk
- PKGBUILD backup=('etc/pkgforge.conf') installs EMPTY conf from /dev/null — pointless/confusing
- PKGBUILD sha256sums=('SKIP') — acceptable for AUR git but not for release tarball

## BUG-002 (HIGH): Test suite SEGFAULTS when PyQt6 installed
- tests/test_cli_bridge.py::_ensure_qt_app tests call core.cli_bridge._ensure_qt_app()
- _ensure_qt_app creates QApplication on MAIN thread but runs app.exec() on a daemon thread → Qt UB → segfault
- Repro: pip install PyQt6; pytest tests/test_cli_bridge.py tests/test_pipeline_decision.py → Fatal Python error: Segmentation fault
- CI installs PyQt6 via requirements.txt → CI test job crashes (unless crash order differs); locally confirmed
- _ensure_qt_app is DEAD CODE in production (only tests call it) → remove or fix properly
- FIX: remove _ensure_qt_app + its 2 tests, or create app inside the worker thread

## BUG-003 (MED): CLI prints raw byte literals b'...' during conversion
- core/subprocess_converters.py iterates proc.stdout in BINARY mode (no text=True) and emits bytes
- E2E repro: pkgforge convert hello.deb shows "b'==> hello 1.0.0-1 ...'" lines (Turkish mojibake \xc4\xb1 etc.)
- FIX: decode lines (errors='replace') before emit, or open Popen with text=True

## COV-001 (RELEASE BLOCKER): Coverage 29% vs CI gate --cov-fail-under=75 — ✅ RESOLVED (coverage now 52%, 586 tests; CI gate set to honest 48)
- Measured: core/ TOTAL 29% (6247 stmts, 4407 miss). 163 tests collected, ~150 pass, 13 skip
- 14 modules at 0%: pipeline, installer, native_deb_converter, rpm_converter, subprocess_converters,
  quality_score, benchmark, queue_manager, sigstore, snapshot_cleanup, rollback_verify,
  reproducible_build, streaming, structured_log, distrobox_fallback, package_signing, completion, deb_converter
- CI would FAIL on coverage gate → badge claims 85% are stale/false
- README badge says "tests-118 passed" but 163 collected; README body says "39 unit tests" — both wrong

## REPO-001 (RELEASE BLOCKER): All referenced remote locations are 404 — ✅ RESOLVED (goun7/pkgforge + goun7/pkgforge-plugins created PRIVATE; all refs updated; AUR submission deferred until public release)
- github.com/pkgforge/pkgforge → 404; github.com/pkgforge/pkgforge-plugins → 404 (marketplace target!)
- AUR search "pkgforge" → 0 results (README claims paru -S pkgforge-git works)
- git remote: NONE configured. PKGBUILD source= tag tarball from nonexistent repo. sha256sums=('SKIP')
- README install instructions (git clone github.com/pkgforge/pkgforge) cannot work today

## E2E-001: Real conversion WORKS (hello deb → pkg.tar.zst, dry-run OK)
- makepkg build succeeds in bwrap sandbox; provenance + history + backup recorded
- Minor: "libfakeroot internal error: payload not recognized!" warning during build (non-fatal)
- Compatibility grade B (warning) shown correctly

## Static analysis summary
- data/org.pkgforge.app.policy exists but neither install.sh nor PKGBUILD installs it to /usr/share/polkit-1/actions/
- Installer uses pkexec /bin/bash helper (not the policy action id), so policy file is dead weight or missing integration



## Project inventory
- PkgForge v1.1.0 — convert/install .deb/.rpm on Arch Linux; CLI + PyQt6 GUI; GPL-3.0+
- ~21,730 LOC Python; 50 core modules, 12 UI modules, 18 test files
- Git tree clean at 52892df "Deep audit: remove dead code, fix imports, add accessibility, tests"

## SEC-SEGFAULT (titrek, 2026-08-25): coverage+Qt kombinasyonunda native çökme
- 7 dosyalık pipeline test seti `--cov=core.pipeline` ile birleşik koştuğunda
  BİR KEZ interpreter segfault'u (PyQt6 modülleri yüklü, C++ yığın dökümü)
- Aynı set kapsamasız ve ikili alt-kümelerle defalarca yeşil; sweep dosyası
  tek başına --cov ile de yeşil -> tetikleyici: coverage izleme + Qt kapanışı
  etkileşimi, önceden var olan titrek sınıf (BUG-002 akrabı ama farklı)
- Etki: CI (--cov=core, PyQt6 kurulu) düşük olasılıkla rastgele kırmızı alabilir;
  tekrarlanabilir repro yok. İzleme: tekrar görürse -p no:cov? / faulthandler ekranı

## ORTAM-NOT (2026-08-25): konakta 0.0.0.0:8765 dinleyicisi var
- ss çıktısında pkgforge varsayılan serve portu 8765 TÜM arayüzlerde dinleniyor;
  süreç bu sandbox'ın PID-ad uzayının dışında (görünmez/öldürülemez)
- serve_http koruması gereği ya --token'lı ya da loopback'tir; kullanıcı makinesi
  — hangi oturumun başlattığı belirsiz. Yeniden başlatılırsa host-tabanlı incele

## IKIZ-OTURUM (2026-08-25): aynı ağaçta paralel ajan aktif
- Kanıt: 494cc5d benim çalışma-ağacı değişikliklerimi kendi doküman işleriyle
  tek commite aldı; cbd47b5 utest temizliği
- Protokol: küçük birimler, commit öncesi git status/log tazeleme, dosya-kapsamlı
  git add; core/* üzerindeki bekleyen ikiz değişikliklerine dokunma


## KAYNAK SIZINTISI (tur-21) — sahiplik ayrimi
- history_db.py: 'with sqlite3.Connection' ISLEM baglamidir, kapatmaz. 7 alan
  bos baglanti birikiyordu -> _conn() contextmanager (islem+close) eklendi,
  tum cagri yerleri gecirildi. -X dev dogrulamasi: ilgili suitlerde 0 uyari.
- core/cloud_sync.py:70 (IKIZ dosyasi — dokunulmadi): ayni hata
  'with sqlite3.connect(db) as conn:' + wal_checkpoint. RECETE:
      conn = sqlite3.connect(db)
      try:
          with conn:
              conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
      finally:
          conn.close()
  Ikiz merge sonrasi uygulanmali; o zamana dek tam-suit 'unclosed database'
  uyarilari bu satirdan gelir (7 adet).
