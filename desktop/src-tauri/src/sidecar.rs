//! Python sidecar management: spawn, JSON-RPC relay, event forwarding.
//!
//! The sidecar speaks line-delimited JSON-RPC 2.0 over stdio. Requests are
//! written to its stdin; a reader thread consumes stdout, routing id-tagged
//! responses to pending oneshot channels and id-less messages to Tauri events
//! (named after the JSON-RPC "method", e.g. "event.log").

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::{AppHandle, Emitter, Manager, State};
use tokio::sync::oneshot;

struct SidecarInner {
    child: Mutex<Option<Child>>,
    stdin: Mutex<Option<ChildStdin>>,
    pending: Mutex<HashMap<u64, oneshot::Sender<serde_json::Value>>>,
}

pub struct Sidecar(Arc<SidecarInner>);

impl Sidecar {
    pub fn new() -> Self {
        Self(Arc::new(SidecarInner {
            child: Mutex::new(None),
            stdin: Mutex::new(None),
            pending: Mutex::new(HashMap::new()),
        }))
    }

    /// Kill the sidecar process (called on app exit).
    pub fn kill(&self) {
        if let Some(child) = self.0.child.lock().unwrap().as_mut() {
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

/// Spawn the Python sidecar and start the stdout reader thread.
pub fn spawn(app: &AppHandle) -> Result<(), String> {
    let root = find_project_root()
        .ok_or_else(|| "PkgForge project root not found (set PKGFORGE_ROOT)".to_string())?;
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
    *state.0.stdin.lock().unwrap() = Some(stdin);
    *state.0.child.lock().unwrap() = Some(child);

    // Reader thread: route responses to pending channels, events to Tauri.
    let inner = state.0.clone();
    let app2 = app.clone();
    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            let Ok(line) = line else { break };
            if line.trim().is_empty() {
                continue;
            }
            let Ok(v) = serde_json::from_str::<serde_json::Value>(&line) else {
                continue;
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
                        let params =
                            v.get("params").cloned().unwrap_or(serde_json::Value::Null);
                        let _ = app2.emit(m, params);
                    }
                }
            }
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
        let mut guard = state.0.stdin.lock().unwrap();
        let stdin = guard.as_mut().ok_or("sidecar not running")?;
        writeln!(stdin, "{msg}").map_err(|e| e.to_string())?;
        stdin.flush().map_err(|e| e.to_string())?;
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
