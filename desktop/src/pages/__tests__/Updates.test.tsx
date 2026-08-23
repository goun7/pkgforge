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

const DELTA = { installed: false, active: false, next_run: "" };
const SCHEDULE = { enabled: false, interval_hours: 24, task: "check_updates", last_run: "", next_run: "" };

/** Route rpc_call responses by method so both cards load cleanly. */
function mockByMethod() {
  invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
    const result =
      payload.method === "schedule.get" ? SCHEDULE :
      payload.method === "delta.status" ? DELTA :
      { ok: true };
    return Promise.resolve({ jsonrpc: "2.0", id: 1, result });
  });
}

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
    mockByMethod();
  });

  it("loads delta status on mount", async () => {
    renderUpdates();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "delta.status" }),
      ),
    );
  });

  it("loads schedule state on mount", async () => {
    renderUpdates();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "schedule.get" }),
      ),
    );
  });

  it("shows the scheduled tasks card", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Devre dışı")).toBeInTheDocument());
    expect(screen.getByText("Zamanlanmış Görevler")).toBeInTheDocument();
  });

  it("toggles the schedule on", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Devre dışı")).toBeInTheDocument());
    // The schedule card's own enable button (second "Etkinleştir" on the page).
    const enableButtons = screen.getAllByText("Etkinleştir");
    fireEvent.click(enableButtons[enableButtons.length - 1]);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "schedule.set", params: expect.objectContaining({ enabled: true }) }),
      ),
    );
  });

  it("has a cross-check input", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByPlaceholderText(/paket adı/i)).toBeInTheDocument());
  });
});
