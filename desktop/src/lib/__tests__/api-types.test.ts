import { describe, expect, it } from "vitest";
import { API_METHODS, READ_METHODS } from "../api-types";

describe("generated api-types (F5.13)", () => {
  it("exposes a substantial method surface", () => {
    expect(API_METHODS.length).toBeGreaterThan(60);
    expect(API_METHODS).toContain("app.version");
    expect(API_METHODS).toContain("pipeline.start");
  });

  it("has no duplicate method names", () => {
    expect(new Set(API_METHODS).size).toBe(API_METHODS.length);
  });

  it("READ_METHODS is a strict subset of API_METHODS", () => {
    const all = new Set<string>(API_METHODS);
    expect(READ_METHODS.length).toBeGreaterThan(0);
    for (const m of READ_METHODS) {
      expect(all.has(m)).toBe(true);
    }
  });

  it("reader scope exposes reads but not mutations", () => {
    expect(READ_METHODS).toContain("settings.get");
    expect(READ_METHODS).toContain("queue.list");
    expect(READ_METHODS).not.toContain("settings.set");
    expect(READ_METHODS).not.toContain("pipeline.start");
  });
});
