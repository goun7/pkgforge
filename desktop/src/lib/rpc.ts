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
import { getLang } from "./lang";
import { tFor } from "./i18n";

let nextId = 1;

/** Faz 8 (8.3): sidecar baglanti durumu takibi. Arka arkaya erisim hatalari
 *  bir "kopuk" durumu bildirir; ilk basarili cagri "duzeldi" der. */
let consecutiveFailures = 0;
type SidecarStatusCb = (ok: boolean) => void;
const sidecarStatusListeners = new Set<SidecarStatusCb>();

/** Sidecar baglanti durumuna abone ol; aboneligi kaldiran fonksiyon doner. */
export function onSidecarStatus(cb: SidecarStatusCb): () => void {
  sidecarStatusListeners.add(cb);
  return () => {
    sidecarStatusListeners.delete(cb);
  };
}

function notifySidecarStatus(ok: boolean): void {
  sidecarStatusListeners.forEach((cb) => cb(ok));
}

/** Faz 8 (3.4): global RPC aktivite takibi (en az bir cagri ucuruluyorsa aktif). */
let inflight = 0;
type ActivityCb = (active: boolean) => void;
const activityListeners = new Set<ActivityCb>();

/** RPC aktivitesine abone ol; aboneligi kaldiran fonksiyon doner. */
export function onRpcActivity(cb: ActivityCb): () => void {
  activityListeners.add(cb);
  return () => {
    activityListeners.delete(cb);
  };
}

function notifyActivity(): void {
  const active = inflight > 0;
  activityListeners.forEach((cb) => cb(active));
}

/** Bir RPC cagrisinin ust siniri: sidecar yanit vermezse UI sonsuz beklemez.
 *  Uzun isler (donusum, SBOM, CVE) zaten hemen {"started":true} dondurup
 *  sonucu event ile bildirir; bu nedenle 60s guvenli bir ust sinirdir. */
const RPC_TIMEOUT_MS = 60000;

function withTimeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(label)), ms);
    p.then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}

/** Call a sidecar method and await its result. */
export async function call<T = unknown>(
  method: string,
  params?: unknown,
  timeoutMs?: number,
): Promise<T> {
  const id = nextId++;
  inflight++;
  notifyActivity();
  try {
  let resp: RpcResponse<T>;
  try {
    resp = await withTimeout(
      invoke<RpcResponse<T>>("rpc_call", {
        id,
        method,
        params: params ?? {},
      }),
      timeoutMs ?? RPC_TIMEOUT_MS,
      `${tFor(getLang())("rpcTimeout")}: ${method}`,
    );
  } catch (err) {
    // Sidecar erisim hatasi (zaman asimi / kopuk baglanti).
    consecutiveFailures++;
    if (consecutiveFailures === 2) notifySidecarStatus(false);
    throw err;
  }
  if (consecutiveFailures > 0) {
    consecutiveFailures = 0;
    notifySidecarStatus(true);
  }
  if (resp.error) {
    throw new Error(`${resp.error.code}: ${resp.error.message}`);
  }
  return resp.result as T;
  } finally {
    inflight--;
    notifyActivity();
  }
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

/** Faz 12: unmount yarışına dayanıklı abonelik bağlayıcısı.
 *
 * Eski desen (`onEvent(...).then((u) => unsubs.push(u))`) erken unmount'ta
 * sızdırıyordu: useEffect cleanup'u listen() promise'i çözülmeden çalışırsa
 * push hiç yapılmaz ve abonelik geri alınamaz. eventBinder() çözülmemiş
 * promise'leri de takip eder; dispose'dan sonra çözülen abonelik anında
 * kaldırılır.
 */
export function eventBinder() {
  let disposed = false;
  const live: UnlistenFn[] = [];
  return {
    /** Abonelik promise'i bağla (onEvent ya da doğrudan listen). */
    bind(subscribe: () => Promise<UnlistenFn>): void {
      // onEvent zaten asla reject etmez; ham listen hatasında sessiz no-op.
      void subscribe().then(
        (un) => {
          if (disposed) un();
          else live.push(un);
        },
        () => {},
      );
    },
    /** Bağlı tüm abonelikleri kaldır (useEffect cleanup'unda çağır). */
    dispose(): void {
      if (disposed) return;
      disposed = true;
      live.forEach((un) => un());
      live.length = 0;
    },
  };
}
