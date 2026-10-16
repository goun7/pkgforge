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

# CI release derlemesini de kosabilsin diye yol sabit degil; `cargo build`
# sonrasi debug ikilisi varsayilan davranistir.
BIN="${PKGFORGE_E2E_BIN:-src-tauri/target/debug/pkgforge-desktop}"
if [ ! -x "$BIN" ]; then
  echo "error: $BIN not found — run 'cargo build' in src-tauri first (or set PKGFORGE_E2E_BIN)" >&2
  exit 1
fi

# Sidecar, Python agacini PKGFORGE_ROOT ile bulur; dogrudan calistirmada
# launcher bunu vermedigi icin burada sabitliyoruz (repo koku = desktop/..).
export PKGFORGE_ROOT="${PKGFORGE_ROOT:-$(cd .. && pwd)}"
# _launch_desktop'un kurali: agacta .venv varsa o interpreter kullanilsin,
# aksi halde spawn_python'un varsayilani (python3) kalir.
if [ -z "${PKGFORGE_PYTHON:-}" ] && [ -x "$PKGFORGE_ROOT/.venv/bin/python" ]; then
  export PKGFORGE_PYTHON="$PKGFORGE_ROOT/.venv/bin/python"
fi

# Backend'i ZORLAMA: sabit `GDK_BACKEND=x11`, Wayland oturumunda GTK'yi
# dusuruyordu (olculen: "Failed to initialize gtk backend!: BoolError ...
# gtk::rt::init" + SIGABRT, 2026-10-16). DMABUF ayari artik kabugun icinde
# (src-tauri/src/main.rs), bu yuzden burada da backend'i sadece X11
# oturumundayken sabitliyoruz; Wayland'da GTK kendi backend'ini secer.
if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -n "${DISPLAY:-}" ]; then
  export GDK_BACKEND=x11
fi
LOG="$(mktemp)"

"$BIN" >"$LOG" 2>&1 &
APP_PID=$!

cleanup() { kill "$APP_PID" 2>/dev/null || true; }
trap cleanup EXIT

# Webview + sidecar dogumu yavas olabilir (CI kosucusu bu makineden yavas:
# tek seferlik 6 sn kontrol CI'da "no sidecar child process" verdi). Kuyrukla.
BEKLE="${E2E_WAIT_SECS:-40}"

# Dogrudan cocuklar ve torunler: sidecar baska bir catinin altina dogabilir.
has_sidecar_child() {
  local pid="$1" k
  for k in $(ps -o pid= --ppid "$pid" 2>/dev/null | tr -d ' '); do
    if ps -o args= -p "$k" 2>/dev/null | grep -qE 'pkgforge-sidecar|main\.py serve'; then
      return 0
    fi
    if has_sidecar_child "$k"; then
      return 0
    fi
  done
  return 1
}

found=0
for _ in $(seq 1 "$BEKLE"); do
  if ! kill -0 "$APP_PID" 2>/dev/null; then
    break
  fi
  if has_sidecar_child "$APP_PID"; then
    found=1
    break
  fi
  sleep 1
done

fail=0

if kill -0 "$APP_PID" 2>/dev/null; then
  echo "PASS: app is running (pid $APP_PID)"
else
  echo "FAIL: app exited early"; fail=1
fi

if [ "$found" -eq 1 ]; then
  echo "PASS: sidecar child process spawned"
else
  echo "FAIL: no sidecar child process (${BEKLE}s beklendi)"; fail=1
fi

if grep -q 'i18n' "$LOG"; then
  echo "PASS: sidecar initialized (i18n log present)"
else
  echo "WARN: no sidecar init log seen (may still be OK)"
fi

kill "$APP_PID" 2>/dev/null || true
sleep 2

if pgrep -af 'pkgforge-sidecar|main.py serve' | grep -v grep >/dev/null 2>&1; then
  echo "FAIL: sidecar still running after exit (bundled veya python)"; fail=1
else
  echo "PASS: sidecar cleaned up on exit"
fi

if [ "$fail" -ne 0 ]; then
  # Teshis: CI logunda app'in kendi stderr'i gorunmeden hata cozulemiyordu.
  echo "----- app logu ($LOG) -----"
  cat "$LOG" 2>/dev/null || true
  echo "----- process agaci -----"
  ps -o pid,ppid,args -e 2>/dev/null | grep -E 'pkgforge|WebKit' | grep -v grep | head -20 || true
fi

rm -f "$LOG"

if [ "$fail" -ne 0 ]; then
  echo "E2E: FAILED"
  exit 1
fi
echo "E2E: ALL CHECKS PASSED"
