import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusPill } from "../StatusPill";

describe("StatusPill (Faz 10 1.6)", () => {
  it("renders localized success label", () => {
    render(<StatusPill status="success" />);
    expect(screen.getByText("Başarılı")).toBeInTheDocument();
  });
  it("renders localized failed label", () => {
    render(<StatusPill status="failed" />);
    expect(screen.getByText("Başarısız")).toBeInTheDocument();
  });
});
