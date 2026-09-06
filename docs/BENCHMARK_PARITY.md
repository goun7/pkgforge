# Conversion Parity Benchmark — PkgForge vs debtap

Date: 2026-09-07 · Fixture: `utest/hello_1.0.0-1_amd64.deb` (script-only package)

## PkgForge (native converter, measured)

| Metric | Value |
|---|---|
| Wall time (`convert --dry-run`, bwrap+fakeroot+makepkg) | **16.9 s** |
| namcap errors | **0** |
| namcap warnings | 1 (`No ELF files and not an "any" package` — benign, fixture has no ELF) |
| Output | `hello-1.0.0-1-x86_64.pkg.tar.zst` + `.provenance.json` + grade B report |

## debtap 3.6.3-1 (installed, NOT measured — blocked)

debtap refuses to run before a root database update:

```console
$ debtap -q hello_1.0.0-1_amd64.deb
Error: You must run at least once "debtap -u" with root privileges
```

Reproduce (needs root once, then re-run):

```bash
sudo debtap -u
cd /tmp/parity && cp <repo>/utest/hello_1.0.0-1_amd64.deb .
time debtap -q hello_1.0.0-1_amd64.deb
namcap hello-*.pkg.tar.zst
```

Compare: wall time, `namcap` error count, and `tar -tf` file lists.
Expected outcome per debtap docs: comparable output, slower (bash + pkgfile
queries); PkgForge differentiates on RPM input, GUI, lifecycle/rollback,
SBOM/provenance and sandboxing — not raw single-deb speed.

## Verdict

Parity claim stays **unproven until the debtap column is filled**. This file
is the protocol; no debtap numbers are invented here.
