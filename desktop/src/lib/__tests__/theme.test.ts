import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

import {
  resolveTheme,
  applyTheme,
  loadTheme,
  applyAccent,
  loadAccentLocal,
  getAccentLocal,
  ACCENTS,
} from "../theme";

function stubMatchMedia(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
}

describe("theme (Faz 9 4.3)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.documentElement.removeAttribute("data-theme");
  });

  it("resolveTheme passes dark through", () => {
    expect(resolveTheme("dark")).toBe("dark");
  });
  it("resolveTheme passes light through", () => {
    expect(resolveTheme("light")).toBe("light");
  });
  it("resolveTheme falls back to dark for unknown", () => {
    expect(resolveTheme("weird")).toBe("dark");
  });
  it("resolveTheme passes oled through", () => {
    expect(resolveTheme("oled")).toBe("oled");
  });
  it("resolveTheme resolves system to light when OS prefers light", () => {
    stubMatchMedia(true);
    expect(resolveTheme("system")).toBe("light");
  });
  it("resolveTheme resolves system to dark when OS prefers dark", () => {
    stubMatchMedia(false);
    expect(resolveTheme("system")).toBe("dark");
  });
  it("resolveTheme falls back to dark when matchMedia is unavailable", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => {
        throw new Error("matchMedia not supported");
      }),
    );
    expect(resolveTheme("system")).toBe("dark");
  });
  it("applyTheme sets the data-theme attribute", () => {
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
  it("applyTheme adds a transient theme-switching class for 400ms", () => {
    vi.useFakeTimers();
    try {
      applyTheme("dark");
      const root = document.documentElement;
      expect(root.classList.contains("theme-switching")).toBe(true);
      vi.advanceTimersByTime(450);
      expect(root.classList.contains("theme-switching")).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });
  it("applyTheme('system') watches OS scheme changes and re-applies live", () => {
    const mq = {
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue(mq));
    applyTheme("system");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(mq.addEventListener).toHaveBeenCalledWith("change", expect.any(Function));
    // OS isik temaya gecer; izleyici data-theme'yi canli gunceller.
    mq.matches = true;
    const handler = mq.addEventListener.mock.calls[0][1] as () => void;
    handler();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    // Yeniden uygulama eski izleyiciyi kaldirip yenisini kaydeder.
    applyTheme("system");
    expect(mq.removeEventListener).toHaveBeenCalledWith("change", handler);
    expect(mq.addEventListener).toHaveBeenCalledTimes(2);
  });
  it("applyTheme('system') tolerates a missing matchMedia watcher", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => {
        throw new Error("matchMedia not supported");
      }),
    );
    expect(() => applyTheme("system")).not.toThrow();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  // --- loadTheme: sidecar ayarlarindan baslangic temasi ---

  it("loadTheme applies the persisted theme from settings", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { theme: "oled" }, error: null });
    await loadTheme();
    expect(document.documentElement.getAttribute("data-theme")).toBe("oled");
    expect(invokeMock).toHaveBeenCalledWith(
      "rpc_call",
      expect.objectContaining({ method: "settings.get" }),
    );
  });
  it("loadTheme ignores a non-string theme value", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { theme: 42 }, error: null });
    await loadTheme();
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });
  it("loadTheme ignores an empty result", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: null, error: null });
    await loadTheme();
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });
  it("loadTheme swallows RPC failures (sidecar not ready)", async () => {
    invokeMock.mockRejectedValue(new Error("sidecar not ready"));
    await expect(loadTheme()).resolves.toBeUndefined();
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });
});

describe("accent (Faz 10 5.1)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });
  afterEach(() => {
    document.documentElement.removeAttribute("data-accent");
    vi.restoreAllMocks();
  });

  it("exposes the five supported accents", () => {
    expect(ACCENTS).toEqual(["blue", "green", "purple", "orange", "rose"]);
  });

  it("applyAccent sets data-accent for non-blue accents and persists the choice", () => {
    applyAccent("green");
    expect(document.documentElement.getAttribute("data-accent")).toBe("green");
    expect(localStorage.getItem("pkgforge.accent")).toBe("green");
  });

  it("applyAccent clears data-accent for the blue default", () => {
    applyAccent("purple");
    applyAccent("blue");
    expect(document.documentElement.hasAttribute("data-accent")).toBe(false);
    expect(localStorage.getItem("pkgforge.accent")).toBe("blue");
  });

  it("applyAccent clears data-accent for unknown accent values", () => {
    applyAccent("purple");
    applyAccent("pink");
    expect(document.documentElement.hasAttribute("data-accent")).toBe(false);
    expect(localStorage.getItem("pkgforge.accent")).toBe("pink");
  });

  it("applyAccent still applies the attribute when localStorage fails", () => {
    vi.spyOn(localStorage, "setItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    expect(() => applyAccent("rose")).not.toThrow();
    expect(document.documentElement.getAttribute("data-accent")).toBe("rose");
  });

  it("loadAccentLocal applies the stored accent at startup", () => {
    localStorage.setItem("pkgforge.accent", "orange");
    loadAccentLocal();
    expect(document.documentElement.getAttribute("data-accent")).toBe("orange");
  });

  it("loadAccentLocal does nothing when nothing is stored", () => {
    loadAccentLocal();
    expect(document.documentElement.hasAttribute("data-accent")).toBe(false);
  });

  it("loadAccentLocal survives a failing localStorage", () => {
    vi.spyOn(localStorage, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    expect(() => loadAccentLocal()).not.toThrow();
    expect(document.documentElement.hasAttribute("data-accent")).toBe(false);
  });

  it("getAccentLocal returns the stored accent", () => {
    localStorage.setItem("pkgforge.accent", "rose");
    expect(getAccentLocal()).toBe("rose");
  });

  it("getAccentLocal falls back to blue for unknown stored values", () => {
    localStorage.setItem("pkgforge.accent", "pink");
    expect(getAccentLocal()).toBe("blue");
  });

  it("getAccentLocal falls back to blue when nothing is stored", () => {
    expect(getAccentLocal()).toBe("blue");
  });

  it("getAccentLocal falls back to blue when localStorage fails", () => {
    vi.spyOn(localStorage, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    expect(getAccentLocal()).toBe("blue");
  });
});
