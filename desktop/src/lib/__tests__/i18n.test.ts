import { describe, expect, it } from "vitest";
import { dict, tFor } from "../i18n";

describe("i18n bridge", () => {
  it("has identical key sets for tr and en", () => {
    expect(Object.keys(dict.en).sort()).toEqual(
      Object.keys(dict.tr).sort(),
    );
  });

  it("returns Turkish defaults and falls back for unknown langs", () => {
    expect(tFor("tr")("profilesTitle")).toBe("Profiller");
    expect(tFor("en")("profilesTitle")).toBe("Profiles");
    expect(tFor("de")("profilesTitle")).toBe("Profiller");
  });

  it("never returns undefined for known keys", () => {
    for (const k of Object.keys(dict.tr) as Array<keyof typeof dict.tr>) {
      const v = tFor("en")(k);
      expect(typeof v).toBe("string");
      expect(v.length).toBeGreaterThan(0);
    }
  });
});
