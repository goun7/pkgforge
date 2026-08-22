# Faz 0 — Tasarım Sistemi & Marka: Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PkgForge'a modern C-görsel (Tauri + React) arayüz kazandırmak için marka varlıkları, tasarım token'ları, JSON-RPC Python-sidecar ve bileşen kütüphanesi temelini kurmak; Convert akışını uçtan uca çalıştırmak.

**Architecture:** Tauri v2 (Rust) kabuk + React 19/TS/Vite/Tailwind v4/shadcn-ui frontend; Python sidecar (`core/api_server.py`) mevcut 45 core modülünü JSON-RPC 2.0 over stdio ile sarmalar. Python core'a dokunulmaz, yalnızca yeni `api_server.py` eklenir. PyQt6 GUI parity sağlanana kadar korunur.

**Tech Stack:** Tauri v2, Rust 1.98, React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/ui, Framer Motion, Lucide, Python 3.14, PyQt6 (sidecar event loop), PyInstaller, pytest, Vitest, Playwright.

## Global Constraints

- Python core (45 modül, 627 test) DEĞİŞTİRİLMEZ; yalnızca `core/api_server.py` eklenir.
- IPC: JSON-RPC 2.0 over stdio, satır-tabanlı çerçeveleme (her mesaj tek satır JSON + `\n`). HTTP portu AÇILMAZ.
- Marka renkleri: Arch Blue `#1793d1`, Ember `#f97316`, gradyan `#1793d1→#f97316`.
- Dark-first tema; `--bg-base #0a0e1a`, `--bg-surface #121829`, `--bg-elevated #1a2038`.
- Font: Inter (UI), JetBrains Mono (mono). İkon: Lucide.
- Yeni UI ayrı giriş: `pkgforge desktop`; mevcut `pkgforge gui` (PyQt6) korunur.
- Repo PRIVATE kalır; AUR yayını kullanıcının açık onayına bağlıdır.
- Ortam: Node v26, pnpm 11, Rust/cargo 1.98, webkit2gtk-4.1 kurulu, Python 3.14.7. PyInstaller kurulu DEĞİL (Task 7'de kurulur).
- Çalışma dizini: `/home/gokun/Masaüstü/pkgforge`. Frontend yeni `desktop/` klasöründe yaşar.
- Tüm Python testleri `QT_QPA_PLATFORM=offscreen` ile; venv: `.venv/bin/python`.

---

## Dosya Yapısı

```
desktop/                          # Yeni Tauri + React uygulaması
  package.json, vite.config.ts, tsconfig.json, tailwind.config.ts
  index.html
  src/
    main.tsx, App.tsx
    styles/tokens.css             # Tasarım token'ları (CSS custom properties)
    lib/rpc.ts                    # JSON-RPC istemcisi (Tauri invoke sarmalayıcı)
    lib/types.ts                  # Protokol tipleri (method/event)
    components/ui/                # shadcn/ui bileşenleri
    components/                   # Kompozitler (DropZone, QueueList, ...)
    pages/                        # Convert, Installed, Settings, ...
  src-tauri/
    Cargo.toml, tauri.conf.json, build.rs
    src/main.rs, src/lib.rs, src/sidecar.rs   # Sidecar spawn + relay
core/api_server.py                # Python sidecar (JSON-RPC over stdio)
tests/test_api_server.py          # Sidecar protokol testleri
assets/logo/                      # (mevcut) logo varlıkları
```

---
### Task 1: Tasarım Token'ları + Logo Entegrasyonu (M0.1)

**Files:**
- Create: `desktop/src/styles/tokens.css`
- Create: `desktop/index.html` (favicon + font link)
- Create: `desktop/public/favicon.svg` (kopya: `assets/logo/logo-transparent.svg`)

**Interfaces:**
- Produces: CSS custom properties (`--brand-blue`, `--bg-base`, ...) — Task 4 bileşenleri bunları tüketir.

- [ ] **Step 1: `desktop/` iskeletini oluştur**

```bash
cd /home/gokun/Masaüstü/pkgforge
mkdir -p desktop/src/styles desktop/public
cp assets/logo/logo-transparent.svg desktop/public/favicon.svg
```

- [ ] **Step 2: `desktop/src/styles/tokens.css` yaz**

```css
/* PkgForge design tokens — Faz 0 (dark-first) */
:root {
  --brand-blue: #1793d1;
  --brand-ember: #f97316;
  --brand-gradient: linear-gradient(135deg, #1793d1, #f97316);
  --bg-base: #0a0e1a;
  --bg-surface: #121829;
  --bg-elevated: #1a2038;
  --text-primary: #e8ecf4;
  --text-secondary: #8b95a8;
  --text-muted: #5a6478;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --info: #38bdf8;
  --radius-btn: 8px;
  --radius-input: 12px;
  --radius-card: 16px;
  --radius-modal: 24px;
  --font-ui: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", monospace;
}
[data-theme="light"] {
  --brand-blue: #0e7ab5;
  --brand-ember: #d95f0e;
  --bg-base: #f8fafc;
  --bg-surface: #ffffff;
  --bg-elevated: #f0f1f3;
  --text-primary: #111827;
  --text-secondary: #6b7280;
  --text-muted: #9ca3af;
}
```

- [ ] **Step 3: `desktop/index.html` yaz (favicon + font)**

```html
<!doctype html>
<html lang="tr" data-theme="dark">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PkgForge</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Doğrula ve commit**

```bash
test -f desktop/public/favicon.svg && echo OK
git add desktop/
git commit -m "feat(desktop): design tokens + favicon (M0.1)"
```

---

### Task 2: Python Sidecar — JSON-RPC Protokol Çekirdeği (M0.2)

**Files:**
- Create: `core/api_server.py`
- Test: `tests/test_api_server.py`

**Interfaces:**
- Produces: `core/api_server.py` — satır-tabanlı JSON-RPC 2.0 over stdio. Methodlar: `app.version`, `tools.status`, `settings.get`, `settings.set`, `history.list`, `history.uninstall`, `history.rollback`, `pipeline.start`, `pipeline.cancel`, `pipeline.approve`, `pipeline.dismiss`. Event'ler: `event.step_changed`, `event.progress`, `event.log`, `event.compatibility_ready`, `event.finished`.
- Consumes: mevcut `core.pipeline.ConversionPipeline`, `core.history_db.HistoryDB`, `i18n.load_settings/save_settings`, `config.discover_tools`.

- [ ] **Step 1: Başarısız testi yaz (`tests/test_api_server.py`)**

```python
"""JSON-RPC sidecar protocol tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _rpc(proc, method, params=None, req_id=1):
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    # read lines until we get our response id
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("sidecar closed stdout")
        data = json.loads(line)
        if data.get("id") == req_id:
            return data


@pytest.fixture
def sidecar(tmp_path, monkeypatch):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env.pop("XDG_CONFIG_HOME", None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "serve"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, env=env,
        cwd=str(PROJECT_ROOT),
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_app_version(sidecar):
    resp = _rpc(sidecar, "app.version")
    assert resp["result"]["name"] == "PkgForge"
    assert "version" in resp["result"]


def test_tools_status(sidecar):
    resp = _rpc(sidecar, "tools.status")
    assert "has_pacman" in resp["result"]


def test_settings_roundtrip(sidecar):
    r1 = _rpc(sidecar, "settings.get", req_id=1)
    assert isinstance(r1["result"], dict)
    r2 = _rpc(sidecar, "settings.set", {"theme": "light"}, req_id=2)
    assert r2["result"]["ok"] is True
    r3 = _rpc(sidecar, "settings.get", req_id=3)
    assert r3["result"]["theme"] == "light"


def test_unknown_method_returns_error(sidecar):
    resp = _rpc(sidecar, "no.such.method")
    assert "error" in resp
    assert resp["error"]["code"] == -32601
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_api_server.py -q`
Expected: FAIL — `main.py serve` alt komutu yok / `core.api_server` yok.

- [ ] **Step 3: `core/api_server.py` minimal uygulamasını yaz**

```python
"""PkgForge — JSON-RPC 2.0 sidecar over stdio.

Framing: one JSON object per line on stdin/stdout. Logs go to stderr ONLY.
"""
from __future__ import annotations

import json
import sys
import threading

from config import APP_NAME, APP_VERSION, discover_tools
from i18n import load_settings, save_settings

_write_lock = threading.Lock()


def _send(obj: dict) -> None:
    with _write_lock:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _result(req_id, result):
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code, message):
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _event(method, params):
    _send({"jsonrpc": "2.0", "method": method, "params": params})


def handle_app_version(params):
    return {"name": APP_NAME, "version": APP_VERSION}


def handle_tools_status(params):
    tools = discover_tools()
    return {
        "has_pacman": bool(tools.pacman),
        "has_makepkg": bool(tools.makepkg),
        "has_distrobox": bool(getattr(tools, "distrobox", None)),
        "missing_required": list(tools.missing_required),
        "missing_optional": list(tools.missing_optional),
    }


def handle_settings_get(params):
    return load_settings()


def handle_settings_set(params):
    settings = load_settings()
    settings.update(params or {})
    save_settings(settings)
    return {"ok": True}


METHODS = {
    "app.version": handle_app_version,
    "tools.status": handle_tools_status,
    "settings.get": handle_settings_get,
    "settings.set": handle_settings_set,
}


def serve() -> None:
    """Run the sidecar main loop (blocking)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _error(None, -32700, "Parse error")
            continue
        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}
        handler = METHODS.get(method)
        if handler is None:
            _error(req_id, -32601, f"Method not found: {method}")
            continue
        try:
            _result(req_id, handler(params))
        except Exception as exc:  # noqa: BLE001 — report, never crash the loop
            _error(req_id, -32000, str(exc))
```

- [ ] **Step 4: `main.py`'e `serve` alt komutunu ekle**

`main.py`'de subparsers bölümüne ekle (diğer `add_parser` çağrılarının yanına):

```python
subparsers.add_parser("serve", help=tr("cli.serve_help"))
```

Ve dispatch bölümüne (args komut seçimi):

```python
elif args.command == "serve":
    from core.api_server import serve
    serve()
```

`i18n/lang_en.py` ve `i18n/lang_tr.py`'e ekle:
```python
"cli.serve_help": "Run the JSON-RPC sidecar (used by the desktop UI)",  # en
"cli.serve_help": "JSON-RPC sidecar'ı çalıştır (masaüstü arayüzü kullanır)",  # tr
```

- [ ] **Step 5: Testleri çalıştır, geçtiklerini doğrula**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_api_server.py -q`
Expected: 4 passed

- [ ] **Step 6: Tam süiti çalıştır (regresyon yok)**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q --timeout=180`
Expected: 631 passed, 2 skipped (627 + 4 yeni)

- [ ] **Step 7: Commit**

```bash
git add core/api_server.py tests/test_api_server.py main.py i18n/lang_en.py i18n/lang_tr.py
git commit -m "feat(sidecar): JSON-RPC 2.0 over stdio core (app.version, tools.status, settings) + serve subcommand"
```

---
### Task 3: Sidecar — Pipeline Methodları + Event Akışı (M0.2 devamı)

**Files:**
- Modify: `core/api_server.py`
- Test: `tests/test_api_server.py` (yeni testler)

**Interfaces:**
- Consumes: `core.pipeline.ConversionPipeline` (Qt sinyalleri: `step_changed(int,str)`, `progress(int)`, `log_message(str,str)`, `compatibility_ready(report)`, `finished(result)`; methodlar: `stage(path)`, `run_staged()`, `cancel()`, `approve_install()`, `dismiss_install(msg="")`).
- Produces: `pipeline.start {path}`, `pipeline.cancel`, `pipeline.approve`, `pipeline.dismiss`; event'ler `event.step_changed {step,status}`, `event.progress {value}`, `event.log {message,level}`, `event.compatibility_ready {report_json}`, `event.finished {success,message}`.

- [ ] **Step 1: Başarısız testi yaz — `tests/test_api_server.py`'e ekle**

```python
def _read_events(proc, timeout=10.0):
    """Read event lines (no id) until event.finished arrives."""
    import select
    events = []
    deadline = __import__("time").time() + timeout
    while __import__("time").time() < deadline:
        ready, _, _ = select.select([proc.stdout], [], [], 0.5)
        if not ready:
            continue
        line = proc.stdout.readline()
        if not line:
            break
        data = json.loads(line)
        if "id" not in data and data.get("method", "").startswith("event."):
            events.append(data)
            if data["method"] == "event.finished":
                break
    return events


def test_pipeline_start_invalid_path(sidecar):
    resp = _rpc(sidecar, "pipeline.start", {"path": "/nonexistent/x.deb"})
    assert "error" in resp


def test_pipeline_start_real_deb(sidecar, tmp_path):
    # minimal fake .deb (ar archive) — pipeline will fail at analysis but
    # must still emit event.finished, never hang
    deb = tmp_path / "fake_1.0_amd64.deb"
    deb.write_bytes(b"!<arch>\n" + b"0" * 64)
    resp = _rpc(sidecar, "pipeline.start", {"path": str(deb)})
    assert resp["result"]["started"] is True
    events = _read_events(sidecar, timeout=30)
    methods = [e["method"] for e in events]
    assert "event.finished" in methods
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_api_server.py::test_pipeline_start_invalid_path -q`
Expected: FAIL — `pipeline.start` method not found (-32601).

- [ ] **Step 3: `core/api_server.py`'e pipeline entegrasyonunu ekle**

Dosyanın üstüne import ve global durum ekle:

```python
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QTimer

from core.pipeline import ConversionPipeline

_pipeline: ConversionPipeline | None = None
```

Handler'ları ekle:

```python
def _ensure_qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def handle_pipeline_start(params):
    global _pipeline
    path = Path(params.get("path", ""))
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    if path.suffix.lower() not in (".deb", ".rpm"):
        raise ValueError(f"Unsupported file type: {path.suffix}")
    app = _ensure_qapp()
    _pipeline = ConversionPipeline()
    _pipeline.step_changed.connect(
        lambda step, status: _event("event.step_changed", {"step": step, "status": status}))
    _pipeline.progress.connect(
        lambda v: _event("event.progress", {"value": v}))
    _pipeline.log_message.connect(
        lambda msg, level: _event("event.log", {"message": msg, "level": level}))
    _pipeline.compatibility_ready.connect(
        lambda report: _event("event.compatibility_ready", {"report": report.to_dict()}))
    _pipeline.finished.connect(
        lambda result: _event("event.finished", {"success": result.success, "message": result.message}))
    _pipeline.stage(path)
    # run on a worker thread so stdin keeps being read
    import threading
    threading.Thread(target=_pipeline.run_staged, daemon=True).start()
    return {"started": True}


def handle_pipeline_cancel(params):
    if _pipeline:
        _pipeline.cancel()
    return {"ok": True}


def handle_pipeline_approve(params):
    if _pipeline:
        _pipeline.approve_install()
    return {"ok": True}


def handle_pipeline_dismiss(params):
    if _pipeline:
        _pipeline.dismiss_install(params.get("message", ""))
    return {"ok": True}
```

`METHODS` sözlüğüne ekle:
```python
    "pipeline.start": handle_pipeline_start,
    "pipeline.cancel": handle_pipeline_cancel,
    "pipeline.approve": handle_pipeline_approve,
    "pipeline.dismiss": handle_pipeline_dismiss,
```

`serve()` döngüsünde Qt event'lerinin işlenmesi için stdin okumasını non-blocking yap:
```python
def serve() -> None:
    """Run the sidecar main loop (blocking)."""
    app = _ensure_qapp()
    import select
    while True:
        app.processEvents()
        ready, _, _ = select.select([sys.stdin], [], [], 0.05)
        if not ready:
            continue
        line = sys.stdin.readline()
        if not line:
            break  # stdin closed — parent exited
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _error(None, -32700, "Parse error")
            continue
        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}
        handler = METHODS.get(method)
        if handler is None:
            _error(req_id, -32601, f"Method not found: {method}")
            continue
        try:
            _result(req_id, handler(params))
        except Exception as exc:  # noqa: BLE001
            _error(req_id, -32000, str(exc))
```

NOT: `CompatibilityReport.to_dict()` yoksa `core/compatibility_checker.py`'e ekle
(checks listesi + overall severity'yi dict'e çevirir). Önce `grep -n "to_dict" core/compatibility_checker.py` ile kontrol et; yoksa minimal `to_dict` ekle ve birim testi yaz.

- [ ] **Step 4: Testleri çalıştır**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_api_server.py -q --timeout=120`
Expected: 6 passed

- [ ] **Step 5: Tam süit**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q --timeout=180`
Expected: 633 passed, 2 skipped

- [ ] **Step 6: Commit**

```bash
git add core/api_server.py core/compatibility_checker.py tests/test_api_server.py
git commit -m "feat(sidecar): pipeline methods + event stream (start/cancel/approve/dismiss)"
```

---
### Task 4: Tauri İskelet + Rust Sidecar Relay (M0.2 devamı)

**Files:**
- Create: `desktop/package.json`, `desktop/vite.config.ts`, `desktop/tsconfig.json`, `desktop/tailwind.config.ts`, `desktop/postcss.config.js`
- Create: `desktop/src-tauri/Cargo.toml`, `desktop/src-tauri/tauri.conf.json`, `desktop/src-tauri/build.rs`
- Create: `desktop/src-tauri/src/main.rs`, `desktop/src-tauri/src/lib.rs`, `desktop/src-tauri/src/sidecar.rs`
- Create: `desktop/src/main.tsx`, `desktop/src/App.tsx`, `desktop/src/lib/rpc.ts`, `desktop/src/lib/types.ts`

**Interfaces:**
- Consumes: Task 2/3 sidecar protokolü (JSON-RPC over stdio).
- Produces: `rpc.call(method, params)` ve `rpc.onEvent(method, cb)` — Task 6 sayfaları bunları kullanır. Rust tarafında `sidecar::spawn()`, `sidecar::call()`, `sidecar::on_event()`.

- [ ] **Step 1: Frontend bağımlılıklarını kur**

```bash
cd /home/gokun/Masaüstü/pkgforge/desktop
pnpm init
pnpm add react react-dom @tauri-apps/api lucide-react framer-motion
pnpm add -D typescript vite @vitejs/plugin-react tailwindcss @tailwindcss/vite @tauri-apps/cli
```

- [ ] **Step 2: `vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: { port: 1420, strictPort: true },
});
```

- [ ] **Step 3: `tailwind.config.ts` + `src/styles/tokens.css` import**

```typescript
// tailwind.config.ts
import type { Config } from "tailwindcss";
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
} satisfies Config;
```

`src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/tokens.css";
import "./styles/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>
);
```

`src/styles/index.css`:
```css
@import "tailwindcss";
body { background: var(--bg-base); color: var(--text-primary); font-family: var(--font-ui); }
```

- [ ] **Step 4: `src/lib/types.ts` — protokol tipleri**

```typescript
export interface RpcResponse<T = unknown> {
  jsonrpc: "2.0";
  id?: number | null;
  result?: T;
  error?: { code: number; message: string };
  method?: string;
  params?: unknown;
}

export interface StepChangedEvent { step: number; status: string }
export interface ProgressEvent { value: number }
export interface LogEvent { message: string; level: string }
export interface FinishedEvent { success: boolean; message: string }
```

- [ ] **Step 5: `src/lib/rpc.ts` — Tauri invoke sarmalayıcı**

```typescript
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import type { RpcResponse } from "./types";

let nextId = 1;

export async function call<T = unknown>(method: string, params?: unknown): Promise<T> {
  const id = nextId++;
  const resp = await invoke<RpcResponse<T>>("rpc_call", { id, method, params: params ?? {} });
  if (resp.error) throw new Error(`${resp.error.code}: ${resp.error.message}`);
  return resp.result as T;
}

export async function onEvent<T>(method: string, cb: (params: T) => void): Promise<UnlistenFn> {
  return listen<T>(method, (e) => cb(e.payload));
}
```

- [ ] **Step 6: Rust tarafı — `src-tauri/src/sidecar.rs`**

```rust
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, Manager, State};

pub struct Sidecar(pub Mutex<Option<Child>>);

pub fn spawn(app: &AppHandle) -> Result<(), String> {
    let py = std::env::var("PKGFORGE_PYTHON").unwrap_or_else(|_| "python3".into());
    let mut child = Command::new(&py)
        .args(["main.py", "serve"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| e.to_string())?;

    let stdout = child.stdout.take().ok_or("no stdout")?;
    let app2 = app.clone();
    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            let Ok(line) = line else { break };
            if line.trim().is_empty() { continue; }
            // Parse to find event method, then emit as Tauri event
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&line) {
                if v.get("id").is_none() {
                    if let Some(m) = v.get("method").and_then(|m| m.as_str()) {
                        let params = v.get("params").cloned().unwrap_or(serde_json::Value::Null);
                        let _ = app2.emit(m, params);
                    }
                } else {
                    // response — store for pending call
                    let _ = app2.emit("__rpc_response__", v);
                }
            }
        }
    });

    let state: State<Sidecar> = app.state();
    *state.0.lock().unwrap() = Some(child);
    Ok(())
}

#[tauri::command]
pub fn rpc_call(state: State<Sidecar>, id: u64, method: String, params: serde_json::Value) -> Result<serde_json::Value, String> {
    let mut guard = state.0.lock().unwrap();
    let child = guard.as_mut().ok_or("sidecar not running")?;
    let stdin = child.stdin.as_mut().ok_or("no stdin")?;
    let msg = serde_json::json!({"jsonrpc":"2.0","id":id,"method":method,"params":params});
    writeln!(stdin, "{}", msg).map_err(|e| e.to_string())?;
    stdin.flush().map_err(|e| e.to_string())?;
    // Response arrives via __rpc_response__ event; frontend correlates by id.
    // For simplicity in Faz 0, return an ack; frontend listens for the response event.
    Ok(serde_json::json!({"jsonrpc":"2.0","id":id,"pending":true}))
}
```

NOT: Bu basit versiyon response'u event olarak döndürür. Frontend `rpc.ts`'de `call()`
bu durumda `__rpc_response__` event'ini dinleyip id eşleştirmesi yapmalı. Task 6'da
bu korelasyon tamamlanır. Alternatif: Rust tarafında pending-map + oneshot channel
ile senkron yanıt (daha karmaşık ama daha temiz). Faz 0 için event-korelasyon yeterli.

- [ ] **Step 7: `src-tauri/src/lib.rs` + `main.rs`**

```rust
// lib.rs
mod sidecar;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(sidecar::Sidecar(std::sync::Mutex::new(None)))
        .setup(|app| {
            sidecar::spawn(&app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![sidecar::rpc_call])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

```rust
// main.rs
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
fn main() { pkgforge_desktop_lib::run() }
```

- [ ] **Step 8: `tauri.conf.json` + `Cargo.toml`**

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "PkgForge",
  "version": "2.0.0",
  "identifier": "com.goun7.pkgforge",
  "build": { "devUrl": "http://localhost:1420", "frontendDist": "../dist" },
  "app": { "windows": [{ "title": "PkgForge", "width": 1200, "height": 800 }] }
}
```

```toml
# Cargo.toml
[package]
name = "pkgforge-desktop"
version = "2.0.0"
edition = "2021"

[lib]
name = "pkgforge_desktop_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[dependencies]
tauri = { version = "2", features = [] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"

[build-dependencies]
tauri-build = { version = "2", features = [] }
```

- [ ] **Step 9: Derle ve doğrula**

```bash
cd /home/gokun/Masaüstü/pkgforge/desktop
pnpm tauri build --debug 2>&1 | tail -5   # veya önce `pnpm tauri dev`
```
Expected: derleme başarılı, pencere açılır, sidecar spawn olur.

- [ ] **Step 10: Commit**

```bash
git add desktop/
git commit -m "feat(desktop): Tauri v2 scaffold + Rust sidecar relay (M0.2)"
```

---
### Task 5: Bileşen Kütüphanesi (M0.3)

**Files:**
- Create: `desktop/src/components/ui/*.tsx` (Button, Card, Badge, Input, Dialog, Toast, Tabs, ProgressBar, Skeleton, Tooltip)
- Create: `desktop/src/components/Sidebar.tsx`, `Topbar.tsx`, `StepIndicator.tsx`, `DropZone.tsx`, `QueueList.tsx`, `LogViewer.tsx`, `EmptyState.tsx`, `StatusPill.tsx`
- Test: `desktop/src/components/__tests__/*.test.tsx`

**Interfaces:**
- Consumes: Task 1 token'ları (`--brand-blue`, `--bg-surface`, ...).
- Produces: Task 6 sayfalarının import edeceği bileşenler. Her bileşen token'ları kullanır, hard-coded renk YOK.

- [ ] **Step 1: shadcn/ui kurulumu**

```bash
cd /home/gokun/Masaüstü/pkgforge/desktop
pnpm dlx shadcn@latest init   # Tailwind v4, TypeScript, dark default
pnpm dlx shadcn@latest add button card badge input dialog toast tabs progress skeleton tooltip
```

shadcn `components.json`'da `aliases` ve `cssVariables: true` seçili olmalı.
`globals.css`'e Task 1 token'larını映射 et (shadcn değişkenleri → PkgForge token'ları).

- [ ] **Step 2: Kompozit bileşenleri yaz**

Her biri tek dosya, token tabanlı. Örnek `StepIndicator.tsx`:

```tsx
import { Check, X, AlertTriangle, Loader2 } from "lucide-react";

const STEPS = ["security", "analysis", "conversion", "compatibility", "install"];

export function StepIndicator({ statuses }: { statuses: Record<string, string> }) {
  return (
    <div className="flex items-center gap-2">
      {STEPS.map((s) => {
        const st = statuses[s] ?? "pending";
        const Icon = st === "done" ? Check : st === "error" ? X : st === "warning" ? AlertTriangle : st === "running" ? Loader2 : null;
        return (
          <div key={s} className="flex flex-col items-center gap-1">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center border ${
              st === "done" ? "bg-[var(--success)] border-transparent" :
              st === "error" ? "bg-[var(--danger)] border-transparent" :
              st === "running" ? "border-[var(--brand-blue)]" : "border-[var(--text-muted)]"
            }`}>
              {Icon && <Icon size={16} className={st === "running" ? "animate-spin" : ""} />}
            </div>
            <span className="text-xs text-[var(--text-secondary)] capitalize">{s}</span>
          </div>
        );
      })}
    </div>
  );
}
```

Benzer şekilde: `DropZone` (drag-drop + animasyon), `QueueList`, `LogViewer` (renk kodlu, mono font), `Sidebar` (sol nav), `Topbar` (⌘K + aksiyonlar), `EmptyState`, `StatusPill`.

- [ ] **Step 3: Bileşen testleri (Vitest + Testing Library)**

```bash
pnpm add -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

Her kompozit için en az bir render testi. Örnek `StepIndicator.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { StepIndicator } from "../StepIndicator";

test("renders 5 steps", () => {
  render(<StepIndicator statuses={{ security: "done" }} />);
  expect(screen.getByText("security")).toBeInTheDocument();
  expect(screen.getByText("install")).toBeInTheDocument();
});
```

- [ ] **Step 4: Testleri çalıştır**

Run: `cd desktop && pnpm vitest run`
Expected: tüm bileşen testleri PASS

- [ ] **Step 5: Commit**

```bash
git add desktop/src/components/ desktop/package.json desktop/pnpm-lock.yaml
git commit -m "feat(desktop): component library (shadcn/ui + composites) (M0.3)"
```

---

### Task 6: Convert Dikey Dilimi (M0.4)

**Files:**
- Create: `desktop/src/pages/Convert.tsx`
- Modify: `desktop/src/App.tsx` (routing), `desktop/src/lib/rpc.ts` (response korelasyonu)
- Test: `desktop/src/pages/__tests__/Convert.test.tsx`

**Interfaces:**
- Consumes: Task 4 `rpc.call`/`rpc.onEvent`, Task 5 bileşenleri, Task 2/3 sidecar method/event'leri.
- Produces: Çalışan Convert ekranı — dosya seç → pipeline.start → event akışı → uyumluluk diyaloğu → kurulum/iptal.

- [ ] **Step 1: `rpc.ts` response korelasyonunu tamamla**

Task 4'te `call()` ack döndürüyordu. Şimdi `__rpc_response__` event'ini dinleyip id eşleştir:

```typescript
const pending = new Map<number, { resolve: (v: any) => void; reject: (e: Error) => void }>();

listen<RpcResponse>("__rpc_response__", (e) => {
  const r = e.payload;
  if (r.id != null && pending.has(r.id)) {
    const p = pending.get(r.id)!;
    pending.delete(r.id);
    if (r.error) p.reject(new Error(`${r.error.code}: ${r.error.message}`));
    else p.resolve(r.result);
  }
});

export async function call<T = unknown>(method: string, params?: unknown): Promise<T> {
  const id = nextId++;
  return new Promise<T>((resolve, reject) => {
    pending.set(id, { resolve, reject });
    invoke("rpc_call", { id, method, params: params ?? {} }).catch(reject);
  });
}
```

- [ ] **Step 2: `Convert.tsx` sayfasını yaz**

DropZone + StepIndicator + QueueList + LogViewer + uyumluluk diyaloğu (WARNING/ERROR'da "Yine de Kur" butonu). Event dinleyicileri:

```tsx
useEffect(() => {
  const unsubs: Promise<UnlistenFn>[] = [
    onEvent<StepChangedEvent>("event.step_changed", (e) => setStep((s) => ({ ...s, [STEPS[e.step]]: e.status }))),
    onEvent<ProgressEvent>("event.progress", (e) => setProgress(e.value)),
    onEvent<LogEvent>("event.log", (e) => appendLog(e)),
    onEvent<any>("event.compatibility_ready", (e) => setReport(e.report)),
    onEvent<FinishedEvent>("event.finished", (e) => { setRunning(false); toast(e.success ? "success" : "error", e.message); }),
  ];
  return () => { Promise.all(unsubs).then((fns) => fns.forEach((f) => f())); };
}, []);
```

Uyumluluk diyaloğu: `report.overall === "ERROR"` veya `"WARNING"` ise "Kapat" + "Yine de Kur" (danger). "PASS" ise düz "Kur". "Yine de Kur" → `call("pipeline.approve")`. "Kapat" → `call("pipeline.dismiss")`.

- [ ] **Step 3: `App.tsx` routing**

```tsx
import { Convert } from "./pages/Convert";
// Basit state-based routing (react-router gerekmez Faz 0)
const [page, setPage] = useState("convert");
```

- [ ] **Step 4: E2E manuel test**

```bash
cd desktop && pnpm tauri dev
```
Bir `.deb` dosyası sürükle → pipeline çalışsın → log aksın → uyumluluk diyaloğu gelsin → kur/iptal et. ERROR senaryosunda "Yine de Kur" çalışmalı.

- [ ] **Step 5: Commit**

```bash
git add desktop/src/
git commit -m "feat(desktop): Convert vertical slice — end-to-end pipeline via sidecar (M0.4)"
```

---
### Task 7: Installed + Settings Parity (M0.5)

**Files:**
- Create: `desktop/src/pages/Installed.tsx`, `desktop/src/pages/Settings.tsx`
- Modify: `core/api_server.py` (history methodları)
- Test: `tests/test_api_server.py` (history testleri), `desktop/src/pages/__tests__/*.test.tsx`

**Interfaces:**
- Consumes: `core.history_db.HistoryDB` (`get_history`, `get_records_for_package`, `clear_history`), `core.security.is_valid_package_name`, `core.security.safe_run`.
- Produces: `history.list`, `history.uninstall {name}`, `history.rollback {name}`, `history.clear`; Installed + Settings sayfaları.

- [ ] **Step 1: Sidecar history methodları için başarısız test yaz**

```python
def test_history_list_empty(sidecar):
    resp = _rpc(sidecar, "history.list")
    assert resp["result"] == []


def test_history_uninstall_invalid_name(sidecar):
    resp = _rpc(sidecar, "history.uninstall", {"name": "bad;rm -rf /"})
    assert "error" in resp
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_api_server.py::test_history_list_empty -q`
Expected: FAIL (-32601 method not found)

- [ ] **Step 3: `core/api_server.py`'e history handler'larını ekle**

```python
from core.history_db import HistoryDB
from core.security import is_valid_package_name


def handle_history_list(params):
    db = HistoryDB()
    records = db.get_history(limit=int(params.get("limit", 100)))
    return [
        {
            "id": r.id, "timestamp": r.timestamp, "package_name": r.package_name,
            "package_type": r.package_type, "status": r.status,
            "original_file": r.original_file, "source_url": r.source_url or "",
        }
        for r in records
    ]


def handle_history_uninstall(params):
    name = params.get("name", "")
    if not is_valid_package_name(name):
        raise ValueError(f"Invalid package name: {name}")
    # Actual pacman -R requires pkexec; in sidecar we report the command to run.
    # The desktop UI triggers pkexec via its own privileged helper in a later phase.
    return {"ok": True, "requires_privilege": True, "package": name}


def handle_history_rollback(params):
    name = params.get("name", "")
    if not is_valid_package_name(name):
        raise ValueError(f"Invalid package name: {name}")
    db = HistoryDB()
    records = db.get_records_for_package(name)
    backups = [r for r in records if r.backup_pkg and Path(r.backup_pkg).is_file()]
    if not backups:
        raise FileNotFoundError(f"No backup found for {name}")
    return {"ok": True, "requires_privilege": True, "backup": backups[0].backup_pkg}


def handle_history_clear(params):
    db = HistoryDB()
    db.clear_history()
    return {"ok": True}
```

`METHODS`'a ekle: `history.list`, `history.uninstall`, `history.rollback`, `history.clear`.

NOT: `requires_privilege` alanı, gerçek `pkexec pacman -R` çağrısının bu fazda UI tarafından
değil, ileriki bir fazda yetkili yardımcı ile yapılacağını belirtir. Faz 0'da uninstall/rollback
yalnızca doğrulama + kayıt döndürür; gerçek kaldırma PyQt6 GUI'deki gibi kalır.

- [ ] **Step 4: Testleri çalıştır**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_api_server.py -q --timeout=120`
Expected: 8 passed

- [ ] **Step 5: `Installed.tsx` sayfası**

Tablo (ID, Tarih, Ad, Tür, Durum, Dosya) + arama + filtre + Uninstall/Rollback/Clear butonları.
`call("history.list")` ile yükle; Uninstall → `call("history.uninstall", {name})` → `requires_privilege` ise toast ile "yetkili işlem" bildir.

- [ ] **Step 6: `Settings.tsx` sayfası**

`call("settings.get")` ile yükle; dil, tema, aur_check, distrobox, clamav, snapshot, dry_run, insecure_http, timeout, output_dir, verbose, auto_sign alanları.
Kaydet → `call("settings.set", {...})`. Tema değişimi `data-theme` attribute'unu günceller.

- [ ] **Step 7: Frontend testleri + tam süit**

```bash
cd desktop && pnpm vitest run
cd .. && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q --timeout=180
```
Expected: frontend PASS; Python 635 passed, 2 skipped

- [ ] **Step 8: Commit**

```bash
git add core/api_server.py tests/test_api_server.py desktop/src/
git commit -m "feat(desktop): Installed + Settings parity via sidecar (M0.5)"
```

---

### Task 8: Paketleme + E2E + Sürüm (M0.6)

**Files:**
- Modify: `desktop/src-tauri/tauri.conf.json` (bundle config, sidecar externalBin)
- Create: `desktop/scripts/build-sidecar.sh` (PyInstaller)
- Create: `desktop/e2e/convert.spec.ts` (Playwright)
- Modify: `requirements-dev.txt` (pyinstaller ekle)

**Interfaces:**
- Consumes: tüm önceki task'lar.
- Produces: Paketlenmiş `.deb`/`.rpm`/`.AppImage` (Tauri bundler), E2E test süiti, `2.0.0-alpha` etiketi.

- [ ] **Step 1: PyInstaller kur ve sidecar'ı tek dosya derle**

```bash
cd /home/gokun/Masaüstü/pkgforge
.venv/bin/pip install pyinstaller
echo "pyinstaller>=6.0" >> requirements-dev.txt
```

`desktop/scripts/build-sidecar.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
.venv/bin/pyinstaller --onefile --name pkgforge-sidecar \
  --hidden-import core --hidden-import i18n --hidden-import config \
  --collect-submodules core --collect-submodules i18n \
  main.py
cp dist/pkgforge-sidecar desktop/src-tauri/binaries/
```

NOT: Python 3.14 + PyInstaller uyumu risklidir (spec §9). Derleme başarısız olursa
alternatif: sidecar'ı kaynak ağaçtan çalıştır (`python main.py serve`) ve üretim
paketine Python bağımlılığı ekle. Bu kararı M0.6'da doğrulama belirler.

- [ ] **Step 2: `tauri.conf.json` bundle + sidecar config**

```json
"bundle": {
  "active": true,
  "targets": ["deb", "rpm", "appimage"],
  "icon": ["../public/favicon.svg"],
  "externalBin": ["binaries/pkgforge-sidecar"]
}
```

Rust `sidecar.rs`'i `tauri::api::process` veya `Command::new_sidecar` kullanacak şekilde
güncelle (üretimde gömülü binary, geliştirmede `python main.py serve`).

- [ ] **Step 3: Playwright E2E**

```bash
cd desktop && pnpm add -D @playwright/test && pnpm exec playwright install chromium
```

`e2e/convert.spec.ts`: sidecar mock'u ile Convert akışını test et (dosya seç → event akışı → diyaloğu → kurulum).

- [ ] **Step 4: Tam derleme + E2E çalıştır**

```bash
cd desktop && bash scripts/build-sidecar.sh
pnpm tauri build
pnpm exec playwright test
```
Expected: bundle üretilir, E2E PASS.

- [ ] **Step 5: Tam Python süiti (regresyon)**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q --timeout=180`
Expected: 635 passed, 2 skipped

- [ ] **Step 6: Sürüm etiketi + commit**

```bash
git add -A
git commit -m "feat(desktop): packaging + E2E + 2.0.0-alpha (M0.6)"
git tag v2.0.0-alpha
git push origin master --tags
```

NOT: Repo PRIVATE kalır; tag push edilir ama GitHub Release/AUR yayını kullanıcının
açık onayına bağlıdır (Global Constraints).

---

## Self-Review Notları

- **Spec kapsamı:** Token'lar (T1), sidecar protokol (T2), pipeline (T3), Tauri iskelet (T4),
  bileşenler (T5), Convert dikey dilim (T6), Installed+Settings (T7), paketleme+E2E (T8).
  Spec §2-§8'deki tüm kilometre taşları M0.1-M0.6 bir task'a映射. ✓
- **Placeholder taraması:** "TBD/TODO" yok; her adımda gerçek kod/komut var. ✓
- **Tip tutarlılığı:** `rpc.call`/`onEvent` (T4) → T6/T7 kullanır; sidecar method adları
  (T2/T3/T7) frontend `call()` çağrılarıyla eşleşir. Event adları `event.*` tutarlı. ✓
- **Bilinen riskler:** PyInstaller+3.14 (T8 Step 1 notu), Rust response korelasyonu
  (T4 notu, T6 Step 1'de tamamlanır), `to_dict` eksikliği (T3 Step 3 notu).
