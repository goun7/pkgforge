// PkgForge desktop — shared live-language store (F5.20).
//
// Settings owns the persisted "language" value; every other page reads it
// through this tiny external store so a change in Settings re-renders all
// mounted pages without prop-drilling. useSyncExternalStore keeps it
// concurrent-safe and test-friendly (no provider needed).
import { useSyncExternalStore } from "react";
import { call } from "./rpc";
import type { Lang } from "./i18n";

let current: Lang = "tr";
const listeners = new Set<() => void>();

function isLang(v: unknown): v is Lang {
  return v === "tr" || v === "en";
}

export function getLang(): Lang {
  return current;
}

export function setLang(lang: Lang): void {
  if (current === lang) return;
  current = lang;
  listeners.forEach((l) => l());
}

/** React hook: subscribe to the live language. */
export function useLang(): Lang {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => {
        listeners.delete(cb);
      };
    },
    () => current,
    () => current,
  );
}

/** Load the persisted language once at startup (best-effort). */
export async function loadLang(): Promise<void> {
  try {
    const s = await call<{ language?: unknown }>("settings.get");
    if (s && isLang(s.language)) setLang(s.language);
  } catch {
    // sidecar not ready yet — keep the Turkish default
  }
}
