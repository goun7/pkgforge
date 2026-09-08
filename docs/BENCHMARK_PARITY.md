# Conversion Parity Benchmark — PkgForge vs debtap

Date: 2026-09-08 (debtap column measured) · Fixture: `utest/hello_1.0.0-1_amd64.deb` (script-only package)

| Metric | PkgForge 2.2.0 (native) | debtap 3.6.3 (`-q`) |
|---|---|---|
| Wall time | **10.0 s** (`convert --dry-run`, bwrap+fakeroot+makepkg) | **6.9 s** |
| namcap errors | **0** | **2** (`custom` license id; missing `bash` dep) |
| namcap warnings | 1 (benign, no ELF in fixture) | 1 (same) |
| Extras | `.provenance.json` + grade B report + license stub | — |

Notes:
- debtap needed `sudo debtap -u` once; on this machine its own DB check is
  buggy with current grep (leading-`*` pattern never matches), so the timed
  run used a copy with only that check fixed — conversion logic untouched.
- debtap is faster on a tiny package (no sandbox); PkgForge trades ~3 s for
  sandbox isolation + zero namcap errors + provenance.
- PkgForge differentiates on RPM input, GUI, lifecycle/rollback,
  SBOM/provenance and sandboxing — not raw single-deb speed.

## Reproduce

```bash
sudo debtap -u
mkdir -p /tmp/parity && cd /tmp/parity && cp <repo>/utest/hello_1.0.0-1_amd64.deb .
time debtap -q hello_1.0.0-1_amd64.deb
namcap hello-*.pkg.tar.zst
```
