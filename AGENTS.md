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

## Bu depoda kapıların gerçek durumu (ölçüldü 2026-10-14)

Yukarıdaki blok ZERON tarafından yönetilir; bu yüzden komut satırları değiştirilmedi.
Yukarıdakileri okurken bilmeniz gerekenler:

- **`npx zeron audit .` tek başına bir kabul kriteri değildir.** `.` verildiğinde araç
  `.venv` içini de tarıyor: depoda ölçülen 526 "critical blocker"ın **401'i `.venv`**
  kaynaklı (satır içi öneriler de kuralla ilgisiz, sablon metin). Araç tek bir yol
  kabul eder, o yüzden ağaç ağaç çalıştırın: `npx zeron audit core`,
  `npx zeron audit desktop/src` (bu ikincisi 100/100 veriyor).
- `core` çıktısındaki 92 bulgu gerçek araçlarla çelişiyor: "bazı yollarda None dönüyor"
  iddialarına karşın `mypy --strict core/` temiz; geniş `except` kullanımı best-effort
  probların tasarımıdır (`# noqa: BLE001`); `random` kullanımı retry jitter'dır
  (güvenlik kararı değil). Bu bulguları "düzeltme" — önce bandit/mypy/ruff ile
  yeniden üretin.
- **Gerçek kapılar:** `make verify` (pytest + %99 coverage eşiği, ruff, mypy --strict,
  bandit -ll), `tools/gen_api_ts.py --check`, `desktop` içinde `tsc -b && vite build`
  ve `vitest run`, `pip-audit` + `pnpm audit --audit-level=high`, `npx zeron scan .`,
  `npx zeron doctor`.
- Bu makinede `pnpm` kullanıcı seviyesindeki `~/pnpm-workspace.yaml` yüzünden proje
  içinden de çalışmaz; frontend kapılarını `/tmp` kopyasında koş (`cp -r desktop
  /tmp/pf_fe && cd /tmp/pf_fe && pnpm install --frozen-lockfile`).

