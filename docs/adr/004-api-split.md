# ADR-004: `core/api_server.py` god-module split into `core/api/*`

Date: 2026-09-07 · Status: accepted

## Context

`core/api_server.py` grew to 1996 lines: JSON-RPC transport, ~90 handlers,
method registry, stdio protocol and the HTTP/LAN server in one module.
Every security review had to read the whole file; the HTTP attack surface
(rate limiting, auth, SSE) could not be reasoned about in isolation.

## Decision

Split by responsibility, keeping **full backward compatibility**:

- `core/api/transport.py` — shared state (pipeline slot, SSE bus, locks),
  JSON-RPC framing (`_send/_result/_error/_event`), thread helpers
- `core/api/handlers_{pipeline,security,system,repo,queue,tools}.py` — handlers
- `core/api/registry.py` — `METHODS` map (incl. `core/http_api/*` re-exports)
- `core/api/protocol.py` — stdio dispatch loop
- `core/api/http.py` — HTTP/LAN transport, rate limiting, OpenAPI
- `core/api_server.py` — thin re-export facade (verified by `dir()` diff:
  zero missing names; only stdlib-helper imports intentionally dropped)

Cross-module calls to patchable/mutable shared state always go through
module-attribute access (`transport._event(...)`, never a copied reference),
so the existing monkeypatch-based tests keep working; tests were retargeted
to canonical homes (`AS.transport.*`, `AS.handlers_queue.*`, `AS.http.*`).

## Consequences

- The split immediately surfaced a real bug: the desktop calls
  `plugin.install`, but `METHODS` had no such entry (fixed in the same change).
- Contract: `core.api_server` import path stays stable; new code imports
  from `core.api.*` directly.
