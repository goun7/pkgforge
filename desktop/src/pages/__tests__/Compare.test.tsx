import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Compare } from "../Compare";
import { ToastProvider } from "../../components/ui/Toast";

function renderCompare() {
  return render(
    <ToastProvider>
      <Compare />
    </ToastProvider>,
  );
}

describe("Compare page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("renders two package path inputs", () => {
    renderCompare();
    expect(screen.getByPlaceholderText(/eski paket/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/yeni paket/i)).toBeInTheDocument();
  });

  it("has a compare button", () => {
    renderCompare();
    expect(screen.getByText("Karşılaştır")).toBeInTheDocument();
  });

  it("calls compare.diff when both paths set", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { started: true } });
    renderCompare();
    fireEvent.change(screen.getByPlaceholderText(/eski paket/i), { target: { value: "/tmp/a.pkg.tar.zst" } });
    fireEvent.change(screen.getByPlaceholderText(/yeni paket/i), { target: { value: "/tmp/b.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Karşılaştır"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "compare.diff" }),
      ),
    );
  });
});
