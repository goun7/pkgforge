# Security Policy

PkgForge converts and installs third-party packages **as root**. We take
reports seriously — thank you for looking.

## Scope

- Supply-chain surfaces: downloader/redirect guard, SSRF host guard,
  marketplace checksum flow, plugin install confirmation
- Privilege boundary: pkexec helper (`scripts/pkgforge-privileged.sh`),
  polkit policy, snapshot/delta systemd units
- Desktop boundary: Tauri IPC (`rpc_call`), `externalBin` sidecar scope,
  Content Security Policy
- Packaging: wheel/sdist contents, PKGBUILD generation, SBOM/provenance

Out of scope: the intentionally unsupported (we will still read it):
social-engineering users into `--yes`, or vulnerabilities in upstream
projects (Arch, Tauri, Python) — report those upstream first.

## How to report

**Do NOT open a public issue for vulnerabilities.** Instead:

1. Mail: the maintainer address on the [profile](https://github.com/goun7)
   with subject `[pkgforge-security]`, or open a
   [private security advisory](https://github.com/goun7/pkgforge/security/advisories/new)
   once Security Advisories are enabled on the repo.
2. Include: affected version/commit, reproduction steps or PoC, impact
   assessment, and (optionally) a suggested fix.
3. You will get a confirmation within **7 days**.

## What happens next

- Triage and severity rating (CVSS-guided), fix on a private branch,
  regression test added to the suite.
- Coordinated release: patched version + `CHANGELOG.md` security entry +
  credit in the release notes (unless you prefer anonymity).
- Project target: critical fixes released within **30 days** of confirmation.

## Hardening already in place (audit starting points)

- 12 documented security layers (`README.md` › Security Architecture)
- SSRF deny-by-default (`allow_private_hosts` opt-in), scheme re-validation
  on every redirect hop, HTTPS-only downloads
- Fail-closed marketplace checksums, explicit remote-code confirmation
- Strict Tauri CSP, capability-scoped `externalBin` sidecar (`["serve"]`)
- SBOM (SPDX + CycloneDX) and SLSA provenance on every release
- Fuzz coverage: downloader/marketplace/name-validation property tests
  (`tests/test_s6_fuzz.py`), CSP strictness locked by CI
