# ADR-005: SSRF deny-by-default + remote-code confirmation

Date: 2026-09-07 · Status: accepted

## Context

PkgForge installs packages as root. Two surfaces accepted
attacker-influenced network input without sufficient gates:

1. `download_package()` followed redirects and fetched any host, including
   intranet/metadata addresses (no SSRF guard — accepted risk since SEC-002).
2. `pkgforge plugin install` downloaded and **executed** remote Python with
   no confirmation at all.

## Decision

- `core/downloader.py::assert_public_host()`: literal-IP check plus
  resolved-DNS check (fail-closed on unresolvable hosts), enforced on the
  initial URL **and every redirect hop**. Opt-in via `allow_private_hosts`
  (CLI setting, default off), threaded through `download_package`,
  `download_with_delta`, marketplace fetches and upstream HEAD checks.
- `pkgforge plugin install` requires `--yes` or an interactive `[y/N]`
  confirmation naming the source repo (mirrors the existing install-confirm
  pattern; non-tty without `--yes` refuses).

## Consequences

- Intranet-mirror users must set one flag; everyone else is protected.
- Unit tests that use fake hosts explicitly opt in (`allow_private_hosts=True`),
  which documents their hermetic intent.
- GPG/minisign pinning for the marketplace stays a documented accepted risk
  (fail-closed SHA-256 + HTTPS + confirm is the enforced baseline).
