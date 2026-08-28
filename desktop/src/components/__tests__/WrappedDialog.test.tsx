import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

import { WrappedDialog } from "../WrappedDialog";

const wrappedReport = {
  year: 2026,
  total: 10,
  success: 8,
  failed: 2,
  success_rate: 80,
  by_type: { deb: 6, rpm: 4 },
  by_month: { "2026-01": 5, "2026-02": 5 },
  top_packages: [{ name: "foo-pkg", count: 3 }],
  distinct_packages: 7,
  busiest_month: "2026-01",
  url_count: 2,
};

describe("WrappedDialog (Faz 10 1.1)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ result: wrappedReport, error: null });
  });

  it("shows the annual summary when open", async () => {
    render(<WrappedDialog open onClose={() => {}} />);
    expect(await screen.findByText("Yıl Özeti")).toBeInTheDocument();
    expect(await screen.findByText("foo-pkg")).toBeInTheDocument();
  });

  it("renders the monthly rhythm chart (Faz 10 5.2)", async () => {
    render(<WrappedDialog open onClose={() => {}} />);
    expect(await screen.findByText("Aylık ritim")).toBeInTheDocument();
  });
});
