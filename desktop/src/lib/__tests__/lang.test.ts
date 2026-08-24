import { describe, expect, it, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { getLang, setLang, useLang } from "../lang";

describe("shared language store (F5.20)", () => {
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
});
