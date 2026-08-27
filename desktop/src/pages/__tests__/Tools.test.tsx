import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Tools } from "../Tools";
import { ToastProvider } from "../../components/ui/Toast";

function renderTools() {
  return render(
    <ToastProvider>
      <Tools />
    </ToastProvider>,
  );
}

describe("Tools page (Feature Tezgahi)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("renders the three tool cards", () => {
    renderTools();
    expect(screen.getByText("RPM → DEB")).toBeInTheDocument();
    expect(screen.getByText("ABI Uyumluluk Denetimi")).toBeInTheDocument();
    expect(screen.getByText("Denetim İzi (Audit)")).toBeInTheDocument();
  });

  it("calls tools.rpm_to_deb when path set and clicked", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { started: true } });
    renderTools();
    fireEvent.change(screen.getByPlaceholderText("/yol/paket.rpm"), {
      target: { value: "/tmp/p.rpm" },
    });
    fireEvent.click(screen.getByText("Donustur"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.rpm_to_deb" }),
      ),
    );
  });

  it("calls tools.abi_check when path set and clicked", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { started: true } });
    renderTools();
    fireEvent.change(screen.getByPlaceholderText("/yol/paket.pkg.tar.zst"), {
      target: { value: "/tmp/p.pkg.tar.zst" },
    });
    fireEvent.click(screen.getByText("Tara"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.abi_check" }),
      ),
    );
  });

  it("loads and shows audit report", async () => {
    const audit = {
      total: 2,
      status_counts: { installed: 2 },
      type_counts: { deb: 2 },
      integrity_issues: 0,
      anomalies: 0,
      records: [],
    };
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: audit });
    renderTools();
    fireEvent.click(screen.getByText("Denetim İzini Yukle"));
    await vi.waitFor(() =>
      expect(screen.getByText(/Toplam 2 kayıt/)).toBeInTheDocument(),
    );
    expect(screen.getByText("installed: 2")).toBeInTheDocument();
  });

  it("shows toast error for empty rpm path", () => {
    renderTools();
    fireEvent.click(screen.getByText("Donustur"));
    expect(invokeMock).not.toHaveBeenCalled();
  });
});
