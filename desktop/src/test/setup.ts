import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

// Faz 9 (4.x): bu jsdom kurulumu localStorage/sessionStorage saglamiyor;
// kalici state'in test edilebilmesi icin bellek-ici surumleriyle degistirilir.
function createMemoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    getItem: (k: string) => (data.has(k) ? (data.get(k) as string) : null),
    setItem: (k: string, v: string) => {
      data.set(k, String(v));
    },
    removeItem: (k: string) => {
      data.delete(k);
    },
    clear: () => {
      data.clear();
    },
    key: (i: number) => Array.from(data.keys())[i] ?? null,
    get length() {
      return data.size;
    },
  };
}
function ensureStorage(name: "localStorage" | "sessionStorage"): void {
  let usable = false;
  try {
    const s = (globalThis as Record<string, unknown>)[name] as Storage | undefined;
    usable = !!s && typeof s.getItem === "function" && typeof s.setItem === "function";
  } catch {
    usable = false;
  }
  if (usable) return;
  const stub = createMemoryStorage();
  try {
    Object.defineProperty(globalThis, name, {
      value: stub,
      configurable: true,
      writable: true,
    });
  } catch {
    (globalThis as Record<string, unknown>)[name] = stub;
  }
}
ensureStorage("localStorage");
ensureStorage("sessionStorage");

// Faz 8: test izolasyonu — her test oncesi depolama temizlenir, boylece
// kalici sayfa state'i / ayarlar testler arasi sizinti yapmaz.
beforeEach(() => {
  try {
    sessionStorage.clear();
    localStorage.clear();
  } catch {
    /* depolama yok */
  }
});

// jsdom does not implement scrollIntoView; stub it for components that
// auto-scroll (LogViewer).
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
