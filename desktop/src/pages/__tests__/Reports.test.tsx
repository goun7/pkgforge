import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Reports } from "../Reports";
import { ToastProvider } from "../../components/ui/Toast";

function renderReports() {
  return render(
    <ToastProvider>
      <Reports />
    </ToastProvider>,
  );
}

const HEALTH = {
  total: 10, installed: 6, converted: 2, failed: 2, success_rate: 80,
  by_type: { deb: 7, rpm: 3 }, by_arch: { x86_64: 10 }, url_count: 4,
  first_seen: "2026-08-01", last_seen: "2026-08-22",
};

describe("Reports page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("loads health stats on mount", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: HEALTH });
    renderReports();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "system.health" }),
      ),
    );
  });

  it("shows success rate", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: HEALTH });
    renderReports();
    await vi.waitFor(() => expect(screen.getByText(/80/)).toBeInTheDocument());
  });

  it("has a benchmark run button", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: HEALTH });
    renderReports();
    await vi.waitFor(() => expect(screen.getByText("Benchmark Çalıştır")).toBeInTheDocument());
  });

  it("has a rollback verify button", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: HEALTH });
    renderReports();
    await vi.waitFor(() => expect(screen.getByText("Rollback Doğrula")).toBeInTheDocument());
  });
});
