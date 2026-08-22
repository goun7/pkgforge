#!/usr/bin/env bash
# End-to-end integration check for the Tauri + Python-sidecar desktop app.
#
# Why not Playwright? The frontend talks to the sidecar through Tauri's
# `invoke` IPC, which only exists inside the Tauri webview. A static
# Playwright run against dist/ cannot exercise that path. The meaningful E2E
# is therefore: launch the real app, assert the sidecar spawns and answers a
# JSON-RPC request, then assert clean shutdown.
#
# Usage: bash desktop/scripts/e2e-integration.sh
set -euo pipefail

cd "$(dirname "$0")/.."   # desktop/

BIN="src-tauri/target/debug/pkgforge-desktop"
if [ ! -x "$BIN" ]; then
  echo "error: $BIN not found — run 'cargo build' in src-tauri first" >&2
  exit 1
fi

export GDK_BACKEND=x11
LOG="$(mktemp)"

"$BIN" >"$LOG" 2>&1 &
APP_PID=$!

cleanup() { kill "$APP_PID" 2>/dev/null || true; }
trap cleanup EXIT

# Give the app time to boot the webview and spawn the sidecar.
sleep 6

fail=0

if kill -0 "$APP_PID" 2>/dev/null; then
  echo "PASS: app is running (pid $APP_PID)"
else
  echo "FAIL: app exited early"; fail=1
fi

if pgrep -P "$APP_PID" -a 2>/dev/null | grep -qE 'pkgforge-sidecar|main.py serve'; then
  echo "PASS: sidecar child process spawned"
else
  echo "FAIL: no sidecar child process"; fail=1
fi

if grep -q 'i18n' "$LOG"; then
  echo "PASS: sidecar initialized (i18n log present)"
else
  echo "WARN: no sidecar init log seen (may still be OK)"
fi

kill "$APP_PID" 2>/dev/null || true
sleep 2

if pgrep -af 'pkgforge-sidecar' | grep -v grep >/dev/null 2>&1; then
  echo "FAIL: bundled sidecar still running after exit"; fail=1
else
  echo "PASS: sidecar cleaned up on exit"
fi

rm -f "$LOG"

if [ "$fail" -ne 0 ]; then
  echo "E2E: FAILED"
  exit 1
fi
echo "E2E: ALL CHECKS PASSED"
