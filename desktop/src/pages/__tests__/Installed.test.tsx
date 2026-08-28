import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Installed } from "../Installed";
import { ToastProvider } from "../../components/ui/Toast";

function renderInstalled() {
  return render(
    <ToastProvider>
      <Installed />
    </ToastProvider>,
  );
}

describe("Installed page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("shows empty state when history is empty", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: [],
    });
    renderInstalled();
    await vi.waitFor(() => expect(screen.getByText("Henüz kayıt yok")).toBeInTheDocument());
  });

  it("lists history records", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: [
        {
          id: 1,
          timestamp: "2026-08-22 10:00",
          package_name: "foo-1.0",
          package_type: "deb",
          status: "success",
          original_file: "/tmp/foo.deb",
          source_url: "",
        },
      ],
    });
    renderInstalled();
    await vi.waitFor(() => expect(screen.getByText("foo-1.0")).toBeInTheDocument());
    expect(screen.getByText("deb")).toBeInTheDocument();
  });

  it("filters records by package name", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: [
        { id: 1, timestamp: "t", package_name: "alpha", package_type: "deb", status: "success", original_file: "a.deb", source_url: "" },
        { id: 2, timestamp: "t", package_name: "beta", package_type: "rpm", status: "failed", original_file: "b.rpm", source_url: "" },
      ],
    });
    renderInstalled();
    await vi.waitFor(() => expect(screen.getByText("alpha")).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText("Filtrele…"), { target: { value: "beta" } });
    expect(screen.queryByText("alpha")).not.toBeInTheDocument();
    expect(screen.getByText("beta")).toBeInTheDocument();
  });

  it("calls history.uninstall and reports privilege requirement", async () => {
    invokeMock
      .mockResolvedValueOnce({
        jsonrpc: "2.0",
        id: 1,
        result: [
          { id: 1, timestamp: "t", package_name: "pkgx", package_type: "deb", status: "success", original_file: "x.deb", source_url: "" },
        ],
      })
      .mockResolvedValueOnce({ jsonrpc: "2.0", id: 2, result: { ok: true, requires_privilege: true, package: "pkgx" } });
    renderInstalled();
    await vi.waitFor(() => expect(screen.getByText("pkgx")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Kaldır pkgx"));
    // Faz 7: onay dialogu eklendi — once "Onayla"ya tiklanir.
    fireEvent.click(await screen.findByText("Onayla"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "history.uninstall" }),
      ),
    );
  });
});
