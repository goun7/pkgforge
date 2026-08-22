#!/usr/bin/env bash
# Build the Python sidecar as a single-file binary and place it where the
# Tauri bundler expects external binaries.
#
# NOTE: Python 3.14 + PyInstaller compatibility was verified with a smoke
# test (see Faz 0 plan, Task 8). If the full PyQt6 build ever fails, fall
# back to shipping the source tree and running `python main.py serve`.
set -euo pipefail

cd "$(dirname "$0")/../.."   # repo root

VENV_PY=".venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "error: $VENV_PY not found — create the venv first" >&2
  exit 1
fi

"$VENV_PY" -m PyInstaller --onefile --name pkgforge-sidecar \
  --hidden-import core --hidden-import i18n --hidden-import config \
  --collect-submodules core --collect-submodules i18n \
  --distpath dist/sidecar --workpath build/sidecar --specpath build \
  main.py

mkdir -p desktop/src-tauri/binaries
cp dist/sidecar/pkgforge-sidecar desktop/src-tauri/binaries/pkgforge-sidecar
echo "sidecar binary ready: desktop/src-tauri/binaries/pkgforge-sidecar"
