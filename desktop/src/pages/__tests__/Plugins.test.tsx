import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Plugins } from "../Plugins";
import { ToastProvider } from "../../components/ui/Toast";

function renderPlugins() {
  return render(
    <ToastProvider>
      <Plugins />
    </ToastProvider>,
  );
}

describe("Plugins page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: [] });
  });

  it("renders installed and available tabs", async () => {
    renderPlugins();
    await vi.waitFor(() => expect(screen.getByText(/Kurulu/)).toBeInTheDocument());
    expect(screen.getByText(/Kullanılabilir/)).toBeInTheDocument();
  });

  it("loads installed plugins on mount", async () => {
    renderPlugins();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "plugin.list" }),
      ),
    );
  });

  it("shows empty message when no installed plugins", async () => {
    renderPlugins();
    await vi.waitFor(() =>
      expect(screen.getByText(/yerel plugin yok/i)).toBeInTheDocument(),
    );
  });
});
