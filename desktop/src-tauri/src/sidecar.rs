//! Python sidecar management: spawn, JSON-RPC relay, event forwarding.
//!
//! The sidecar speaks line-delimited JSON-RPC 2.0 over stdio. Requests are
//! written to its stdin; a reader thread consumes stdout, routing id-tagged
//! responses to pending oneshot channels and id-less messages to Tauri events
//! (named after the JSON-RPC "method", e.g. "event/log").

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;
use tokio::sync::oneshot;

struct SidecarInner {
    /// Production path: Tauri shell-plugin child (externalBin sidecar).
    /// `CommandChild` is neither Clone nor shared; calls take/borrow it
    /// through this mutex (`kill` takes ownership out).
    shell_child: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
    /// Dev fallback path: manually spawned `python main.py serve`.
    legacy_child: Mutex<Option<Child>>,
    legacy_stdin: Mutex<Option<ChildStdin>>,
    pending: Mutex<HashMap<u64, oneshot::Sender<serde_json::Value>>>,
}

pub struct Sidecar(Arc<SidecarInner>);

impl Sidecar {
    pub fn new() -> Self {
        Self(Arc::new(SidecarInner {
            shell_child: Mutex::new(None),
            legacy_child: Mutex::new(None),
            legacy_stdin: Mutex::new(None),
            pending: Mutex::new(HashMap::new()),
        }))
    }

    /// Kill the sidecar process (called on app exit).
    pub fn kill(&self) {
        if let Some(child) = self.0.shell_child.lock().unwrap().take() {
            let _ = child.kill();
        }
        if let Some(child) = self.0.legacy_child.lock().unwrap().as_mut() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// Locate the PkgForge project root (a directory containing main.py).
fn find_project_root() -> Option<PathBuf> {
    if let Ok(root) = std::env::var("PKGFORGE_ROOT") {
        let p = PathBuf::from(root);
        if p.join("main.py").is_file() {
            return Some(p);
        }
    }
    for cand in [".", "..", "../.."] {
        let p = PathBuf::from(cand);
        if p.join("main.py").is_file() {
            return Some(p.canonicalize().unwrap_or(p));
        }
    }
    None
}

/// Route one complete JSON-RPC line to pending calls or Tauri events.
/// Shared by the shell-plugin reader task and the legacy reader thread.
fn route_line(
    inner: &Arc<SidecarInner>,
    app: &AppHandle,
    line: &str,
) {
    let line = line.trim();
    if line.is_empty() {
        return;
    }
    let Ok(v) = serde_json::from_str::<serde_json::Value>(line) else {
        return;
    };
    match v.get("id") {
        Some(id) if id.is_u64() => {
            let id = id.as_u64().unwrap_or(0);
            let sender = inner.pending.lock().unwrap().remove(&id);
            if let Some(tx) = sender {
                let _ = tx.send(v);
            }
        }
        _ => {
            if let Some(m) = v.get("method").and_then(|m| m.as_str()) {
                let params = v.get("params").cloned().unwrap_or(serde_json::Value::Null);
                let _ = app.emit(m, params);
            }
        }
    }
}

/// Spawn the bundled sidecar through the Tauri shell plugin
/// (`externalBin`, capability-scoped to `["serve"]`).
fn spawn_bundled(app: &AppHandle) -> Result<(), String> {
    let (mut rx, child) = app
        .shell()
        .sidecar("pkgforge-sidecar")
        .map_err(|e| format!("sidecar binary not found: {e}"))?
        .args(["serve"])
        .spawn()
        .map_err(|e| format!("failed to spawn bundled sidecar: {e}"))?;

    let state: State<Sidecar> = app.state();
    *state.0.shell_child.lock().unwrap() = Some(child);

    // Reader task: shell-plugin stdout arrives in arbitrary chunks, so
    // buffer until newline before routing complete JSON-RPC lines.
    let inner = state.0.clone();
    let app2 = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut buf = String::new();
        while let Some(event) = rx.recv().await {
            if let CommandEvent::Stdout(chunk) = event {
                buf.push_str(&String::from_utf8_lossy(&chunk));
                while let Some(pos) = buf.find('\n') {
                    let line: String = buf.drain(..=pos).collect();
                    route_line(&inner, &app2, &line);
                }
            }
        }
        // stdout closed: sidecar exited. Fail all pending calls.
        inner.pending.lock().unwrap().clear();
    });
    Ok(())
}

/// Spawn the Python sidecar and start the stdout reader thread.
///
/// Prefers a bundled single-file binary (production); falls back to running
/// `python main.py serve` from the source tree (development).
pub fn spawn(app: &AppHandle) -> Result<(), String> {
    // PKGFORGE_SIDECAR=python: bundled binary yerine kaynak agacindaki guncel
    // Python sidecar'i kullan (bundled sidecar eski kalabilir; kaynak-koku/dev).
    if std::env::var("PKGFORGE_SIDECAR").as_deref() != Ok("python") {
        // Bundled sidecar present (production build)? Otherwise fall through
        // to the python dev fallback below. NOTE: `sidecar()` only resolves
        // the path, it does not check existence — check explicitly.
        if find_bundled_sidecar() {
            return spawn_bundled(app);
        }
    }
    spawn_python(app)
}

/// True when a bundled sidecar binary exists on disk.
///
/// Checks the production layout (next to the executable, triple already
/// stripped by the bundler) and the dev layout
/// (`src-tauri/binaries/pkgforge-sidecar-<triple>`, exe at
/// `src-tauri/target/{debug,release}/`).
fn find_bundled_sidecar() -> bool {
    let triple = std::env::var("TAURI_ENV_TARGET_TRIPLE").unwrap_or_default();
    let suffixed = if triple.is_empty() {
        String::from("pkgforge-sidecar")
    } else {
        format!("pkgforge-sidecar-{triple}")
    };
    let Ok(exe) = std::env::current_exe() else {
        return false;
    };
    let Some(dir) = exe.parent() else {
        return false;
    };
    if dir.join("pkgforge-sidecar").is_file() {
        return true;
    }
    // dev layout: <root>/src-tauri/target/{debug,release} -> <root>/src-tauri/binaries/
    if dir.join("../../binaries").join(&suffixed).is_file() {
        return true;
    }
    false
}

/// Dev fallback: spawn `python main.py serve` from the source tree.
fn spawn_python(app: &AppHandle) -> Result<(), String> {
    let root = find_project_root().ok_or_else(|| {
        "PkgForge sidecar not found (bundle pkgforge-sidecar or set PKGFORGE_ROOT)".to_string()
    })?;
    let py = std::env::var("PKGFORGE_PYTHON").unwrap_or_else(|_| "python3".into());
    let mut child = Command::new(&py)
        .args(["main.py", "serve"])
        .current_dir(&root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar ({py}): {e}"))?;

    let stdout = child.stdout.take().ok_or("sidecar stdout missing")?;
    let stdin = child.stdin.take().ok_or("sidecar stdin missing")?;

    let state: State<Sidecar> = app.state();
    *state.0.legacy_stdin.lock().unwrap() = Some(stdin);
    *state.0.legacy_child.lock().unwrap() = Some(child);

    // Reader thread: route responses to pending channels, events to Tauri.
    let inner = state.0.clone();
    let app2 = app.clone();
    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            let Ok(line) = line else { break };
            route_line(&inner, &app2, &line);
        }
        // stdout closed: sidecar exited. Fail all pending calls.
        let mut pending = inner.pending.lock().unwrap();
        pending.clear();
    });

    Ok(())
}

/// Frontend entry point: send a JSON-RPC request, await the response.
#[tauri::command]
pub async fn rpc_call(
    state: State<'_, Sidecar>,
    id: u64,
    method: String,
    params: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let (tx, rx) = oneshot::channel();
    state.0.pending.lock().unwrap().insert(id, tx);

    let msg = serde_json::json!({
        "jsonrpc": "2.0",
        "id": id,
        "method": method,
        "params": params,
    });
    {
        if let Some(child) = state.0.shell_child.lock().unwrap().as_mut() {
            let line = format!("{msg}\n");
            child.write(line.as_bytes()).map_err(|e| e.to_string())?;
        } else {
            let mut guard = state.0.legacy_stdin.lock().unwrap();
            let stdin = guard.as_mut().ok_or("sidecar not running")?;
            writeln!(stdin, "{msg}").map_err(|e| e.to_string())?;
            stdin.flush().map_err(|e| e.to_string())?;
        }
    }

    match tokio::time::timeout(Duration::from_secs(120), rx).await {
        Ok(Ok(v)) => Ok(v),
        Ok(Err(_)) => Err("sidecar closed the connection".into()),
        Err(_) => {
            state.0.pending.lock().unwrap().remove(&id);
            Err("sidecar response timeout".into())
        }
    }
}
