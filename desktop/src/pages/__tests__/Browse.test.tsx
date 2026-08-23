import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Browse } from "../Browse";
import { ToastProvider } from "../../components/ui/Toast";

function renderBrowse() {
  return render(
    <ToastProvider>
      <Browse />
    </ToastProvider>,
  );
}

describe("Browse page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { started: true } });
  });

  it("renders the search input and button", () => {
    renderBrowse();
    expect(screen.getByPlaceholderText(/AUR'da ara/i)).toBeInTheDocument();
    expect(screen.getByText("Ara")).toBeInTheDocument();
  });

  it("calls aur.search when searching", async () => {
    renderBrowse();
    fireEvent.change(screen.getByPlaceholderText(/AUR'da ara/i), { target: { value: "firefox" } });
    fireEvent.click(screen.getByText("Ara"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "aur.search" }),
      ),
    );
  });

  it("does not search with empty query", async () => {
    renderBrowse();
    fireEvent.click(screen.getByText("Ara"));
    expect(invokeMock).not.toHaveBeenCalled();
  });
});
