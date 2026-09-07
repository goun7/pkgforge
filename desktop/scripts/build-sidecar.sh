#!/usr/bin/env bash
# Build the Python sidecar as a single-file binary and place it where the
# Tauri bundler expects external binaries:
#   desktop/src-tauri/binaries/pkgforge-sidecar-<target-triple>
# (externalBin requires the triple suffix; the bundler strips it and ships
#  the binary executable. See https://v2.tauri.app/develop/sidecar/)
#
# NOTE: Python 3.14 + PyInstaller compatibility was verified with a smoke
# test (see Faz 0 plan, Task 8). If the full PyQt6 build ever fails, fall
# back to shipping the source tree and running `python main.py serve`.
set -euo pipefail

cd "$(dirname "$0")/../.."   # repo root

VENV_PY="${VENV_PY:-.venv/bin/python}"
if ! command -v "$VENV_PY" >/dev/null 2>&1; then
  echo "error: $VENV_PY not found — create the venv first (or set VENV_PY)" >&2
  exit 1
fi

if command -v rustc >/dev/null 2>&1; then
  TRIPLE="$(rustc --print host-tuple 2>/dev/null || rustc -Vv | grep '^host:' | cut -f2 -d' ')"
else
  echo "error: rustc not found — cannot determine target triple" >&2
  exit 1
fi
if [ -z "${TRIPLE:-}" ]; then
  echo "error: could not determine target triple" >&2
  exit 1
fi

"$VENV_PY" -m PyInstaller --onefile --name pkgforge-sidecar \
  --hidden-import core --hidden-import i18n --hidden-import config \
  --collect-submodules core --collect-submodules i18n \
  --distpath dist/sidecar --workpath build/sidecar --specpath build \
  main.py

mkdir -p desktop/src-tauri/binaries
OUT="desktop/src-tauri/binaries/pkgforge-sidecar-${TRIPLE}"
cp dist/sidecar/pkgforge-sidecar "$OUT"
chmod +x "$OUT"
echo "sidecar binary ready: $OUT"
