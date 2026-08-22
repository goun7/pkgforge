import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(() => Promise.resolve(null)),
}));

import { Export } from "../Export";
import { ToastProvider } from "../../components/ui/Toast";

function renderExport() {
  return render(
    <ToastProvider>
      <Export />
    </ToastProvider>,
  );
}

describe("Export page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    // flatpak_list returns empty by default on mount
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: [] });
  });

  it("renders the three export cards", async () => {
    renderExport();
    await vi.waitFor(() => expect(screen.getByText(/AppImage/)).toBeInTheDocument());
    expect(screen.getByText(/Flatpak/)).toBeInTheDocument();
    expect(screen.getByText(/OCI/)).toBeInTheDocument();
  });

  it("loads flatpak app list on mount", async () => {
    renderExport();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "export.flatpak_list" }),
      ),
    );
  });

  it("shows empty flatpak message when no apps", async () => {
    renderExport();
    await vi.waitFor(() =>
      expect(screen.getByText(/Flatpak uygulaması bulunamadı/i)).toBeInTheDocument(),
    );
  });
});
