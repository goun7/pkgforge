import { describe, expect, it, vi, afterEach } from "vitest";
import { resolveTheme, applyTheme } from "../theme";

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
  it("applyTheme sets the data-theme attribute", () => {
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
