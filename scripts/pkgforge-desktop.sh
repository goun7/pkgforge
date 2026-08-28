#!/usr/bin/env bash
# PkgForge modern masaustu UI (Tauri + React) baslatici.
# Tauri binary sidecar olarak `python main.py serve` spawn eder; bunun icin
# proje kokunu (PKGFORGE_ROOT) ve bagimliliklarin oldugu venv python'ini
# (PKGFORGE_PYTHON) bilir. Bu script ikisini de otomatik ayarlar.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PKGFORGE_ROOT="$ROOT"
export PKGFORGE_PYTHON="${PKGFORGE_PYTHON:-$ROOT/.venv/bin/python}"
# Kaynak agacindaki guncel Python sidecar'i kullan (bundled binary eski olabilir).
export PKGFORGE_SIDECAR="${PKGFORGE_SIDECAR:-python}"
# Wayland + webkit2gtk: DMABUF renderer "GBM buffer" hatasi ve Error 71
# (protokol) verip pencereyi bos/minimize birakiyor; kapatarak native Wayland kullan.
export WEBKIT_DISABLE_DMABUF_RENDERER="${WEBKIT_DISABLE_DMABUF_RENDERER:-1}"

BIN="$ROOT/desktop/src-tauri/target/release/pkgforge-desktop"
if [ ! -x "$BIN" ]; then
  echo "Hata: Tauri binary bulunamadi: $BIN" >&2
  echo "Once derleyin: cd desktop && pnpm tauri build --no-bundle" >&2
  exit 1
fi
if [ ! -x "$PKGFORGE_PYTHON" ]; then
  echo "Hata: venv python bulunamadi: $PKGFORGE_PYTHON" >&2
  echo "Once: python -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 1
fi

exec "$BIN" "$@"
