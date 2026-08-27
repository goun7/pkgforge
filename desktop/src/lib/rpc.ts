/** JSON-RPC client over the Tauri sidecar relay.
 *
 * Requests go through the Rust `rpc_call` command, which writes one JSON
 * line to the sidecar's stdin and resolves with the full JSON-RPC response
 * once the matching id comes back on stdout. Push events (`event.*`) are
 * forwarded by the Rust reader thread as Tauri events.
 */
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import type { RpcResponse } from "./types";

let nextId = 1;

/** Call a sidecar method and await its result. */
export async function call<T = unknown>(
  method: string,
  params?: unknown,
): Promise<T> {
  const id = nextId++;
  const resp = await invoke<RpcResponse<T>>("rpc_call", {
    id,
    method,
    params: params ?? {},
  });
  if (resp.error) {
    throw new Error(`${resp.error.code}: ${resp.error.message}`);
  }
  return resp.result as T;
}

/** Subscribe to a sidecar push event (e.g. "event/log").
 *
 * Never rejects: a failed subscription returns a no-op unlisten instead of
 * surfacing an unhandled promise rejection at every `.then(...)` call site.
 */
export async function onEvent<T>(
  method: string,
  cb: (params: T) => void,
): Promise<UnlistenFn> {
  try {
    return await listen<T>(method, (e) => cb(e.payload));
  } catch {
    return () => {};
  }
}
