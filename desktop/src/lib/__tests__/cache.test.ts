import { describe, expect, it, vi, afterEach } from "vitest";
import { cacheGet, cacheSet, cacheInvalidate } from "../cache";

describe("cache (Faz 9 4.2)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns null for a missing key", () => {
    expect(cacheGet("missing-key-xyz", 1000)).toBeNull();
  });

  it("stores and retrieves a value within ttl", () => {
    cacheSet("k1", { a: 1 });
    expect(cacheGet("k1", 60000)).toEqual({ a: 1 });
  });

  it("expires a value after ttl", () => {
    vi.useFakeTimers();
    cacheSet("k2", "v");
    vi.advanceTimersByTime(100);
    expect(cacheGet("k2", 50)).toBeNull();
  });

  it("invalidate drops a key", () => {
    cacheSet("k3", "v");
    cacheInvalidate("k3");
    expect(cacheGet("k3", 60000)).toBeNull();
  });
});
