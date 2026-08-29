import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

import { getLang, setLang, useLang, loadLang } from "../lang";

describe("shared language store (F5.20)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });
  afterEach(() => {
    act(() => setLang("tr"));
  });

  it("defaults to Turkish", () => {
    expect(getLang()).toBe("tr");
  });

  it("setLang updates the value and notifies subscribers", () => {
    const { result } = renderHook(() => useLang());
    expect(result.current).toBe("tr");
    act(() => setLang("en"));
    expect(result.current).toBe("en");
    expect(getLang()).toBe("en");
  });

  it("setting the same language is a no-op (no extra notify)", () => {
    const { result } = renderHook(() => useLang());
    let renders = 0;
    const probe = renderHook(() => {
      renders += 1;
      return useLang();
    });
    const before = renders;
    act(() => setLang(result.current));
    expect(probe.result.current).toBe(result.current);
    expect(renders).toBe(before);
  });

  it("useLang unsubscribes on unmount", () => {
    const { result, unmount } = renderHook(() => useLang());
    expect(result.current).toBe("tr");
    unmount();
    // Ayrilan abone bildirimleri patlatmaz; yeni aboneler degeri gorur.
    expect(() => act(() => setLang("en"))).not.toThrow();
    const fresh = renderHook(() => useLang());
    expect(fresh.result.current).toBe("en");
  });

  // --- loadLang: baslangicta kalici dili sidecar'dan yukle ---

  it("loadLang applies the persisted language and notifies subscribers", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { language: "en" }, error: null });
    const { result } = renderHook(() => useLang());
    await act(async () => {
      await loadLang();
    });
    expect(getLang()).toBe("en");
    expect(result.current).toBe("en");
    expect(invokeMock).toHaveBeenCalledWith(
      "rpc_call",
      expect.objectContaining({ method: "settings.get" }),
    );
  });

  it("loadLang keeps Turkish for an unknown language code", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { language: "de" }, error: null });
    await act(async () => {
      await loadLang();
    });
    expect(getLang()).toBe("tr");
  });

  it("loadLang keeps Turkish when settings lack a language field", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: {}, error: null });
    await act(async () => {
      await loadLang();
    });
    expect(getLang()).toBe("tr");
  });

  it("loadLang keeps Turkish when the result is empty", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: null, error: null });
    await act(async () => {
      await loadLang();
    });
    expect(getLang()).toBe("tr");
  });

  it("loadLang swallows RPC failures (sidecar not ready)", async () => {
    invokeMock.mockRejectedValue(new Error("sidecar not ready"));
    await act(async () => {
      await expect(loadLang()).resolves.toBeUndefined();
    });
    expect(getLang()).toBe("tr");
  });
});
