import { describe, expect, it } from "vitest";
import { plural, fmtNumber, fmtDate } from "../format";

describe("format helpers (Faz 9 4.1)", () => {
  it("plural singular keeps singular form", () => {
    expect(plural(1, "kayıt", "kayıtlar")).toBe("1 kayıt");
  });
  it("plural multiple uses plural form", () => {
    expect(plural(5, "kayıt", "kayıtlar")).toBe("5 kayıtlar");
  });
  it("plural without count omits the number", () => {
    expect(plural(3, "item", "items", false)).toBe("items");
  });
  it("fmtNumber formats tr with dot separator", () => {
    expect(fmtNumber(1234, "tr")).toBe("1.234");
  });
  it("fmtNumber formats en with comma separator", () => {
    expect(fmtNumber(1234, "en")).toBe("1,234");
  });
  it("fmtDate returns raw value for invalid input", () => {
    expect(fmtDate("not-a-date", "en")).toBe("not-a-date");
  });
  it("fmtDate formats a valid date", () => {
    expect(fmtDate("2026-08-15T10:00:00Z", "en")).toContain("2026");
  });
});
