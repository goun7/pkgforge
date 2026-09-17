# 🛡️ ZERON Deterministic Verification Protocol
<!-- ZERON-AGENT-RULES:START -->
This project is guarded by **ZERON** (Deterministic Multi-Role Agent Verification Rig).
All AI coding agents (Cursor, Claude Code, Devin, Antigravity) must adhere to these invariant rules:

1. **Dead Button & Stub Linter:** Never leave empty click handlers `() => {}` or unhandled async calls. Always verify with:
   `npx zeron scan .`
2. **Contract Parity:** Ensure frontend payload keys match backend REST, GraphQL, and gRPC definitions:
   `npx zeron audit .`
3. **Healthcard Probe Tour:** Confirm system integrity across all 22 verification engines:
   `npx zeron doctor`
4. **Cryptographic Proof of Execution (PoE):** Git commits will be blocked without a matching cryptographic seal. Sign tests before committing:
   `npx zeron sign-proof "<test-command>"`
<!-- ZERON-AGENT-RULES:END -->
