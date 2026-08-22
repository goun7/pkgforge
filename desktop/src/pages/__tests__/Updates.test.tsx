import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Updates } from "../Updates";
import { ToastProvider } from "../../components/ui/Toast";

function renderUpdates() {
  return render(
    <ToastProvider>
      <Updates />
    </ToastProvider>,
  );
}

describe("Updates page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("loads delta status on mount", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: { installed: false, active: false, next_run: "" },
    });
    renderUpdates();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "delta.status" }),
      ),
    );
  });

  it("shows enable and disable buttons", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: { installed: false, active: false, next_run: "" },
    });
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Etkinleştir")).toBeInTheDocument());
    expect(screen.getByText("Kapat")).toBeInTheDocument();
  });

  it("reports privilege requirement on enable", async () => {
    invokeMock
      .mockResolvedValueOnce({ jsonrpc: "2.0", id: 1, result: { installed: false, active: false, next_run: "" } })
      .mockResolvedValueOnce({ jsonrpc: "2.0", id: 2, result: { ok: false, requires_privilege: true, message: "pkexec" } });
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Etkinleştir")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Etkinleştir"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "delta.enable" }),
      ),
    );
  });

  it("has a cross-check input", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: { installed: false, active: false, next_run: "" },
    });
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByPlaceholderText(/paket adı/i)).toBeInTheDocument());
  });
});
