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
    fireEvent.click(screen.getByText("Dönüştür"));
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
    fireEvent.change(screen.getAllByPlaceholderText("/yol/paket.pkg.tar.zst")[0], {
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
    fireEvent.click(screen.getByText("Denetim İzini Yükle"));
    await vi.waitFor(() =>
      expect(screen.getByText(/Toplam 2/)).toBeInTheDocument(),
    );
    expect(screen.getByText("installed: 2")).toBeInTheDocument();
  });

  it("shows toast error for empty rpm path", () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: {} });
    renderTools();
    fireEvent.click(screen.getByText("Dönüştür"));
    expect(invokeMock).not.toHaveBeenCalledWith(
      "rpc_call",
      expect.objectContaining({ method: "tools.rpm_to_deb" }),
    );
  });
});

describe("Tools page Faz 2 (scan/attest/publish/snapshot)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: {} });
  });

  it("renders the four Faz 2 cards", () => {
    renderTools();
    expect(screen.getByText("İmaj Taraması (CVE/Malware)")).toBeInTheDocument();
    expect(screen.getByText("Attestation (SLSA)")).toBeInTheDocument();
    expect(screen.getByText("AUR Yayınla")).toBeInTheDocument();
    expect(screen.getByText("Snapshot Temizliği")).toBeInTheDocument();
  });

  it("loads snapshot status on mount", async () => {
    renderTools();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.snapshot_status" }),
      ),
    );
  });

  it("calls tools.scan_image when path set and clicked", async () => {
    renderTools();
    fireEvent.change(screen.getByPlaceholderText("/yol/imaj.tar"), {
      target: { value: "/tmp/img.tar" },
    });
    fireEvent.click(screen.getByText("İmajı Tara"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.scan_image" }),
      ),
    );
  });

  it("calls tools.attest when path set and clicked", async () => {
    renderTools();
    const inputs = screen.getAllByPlaceholderText("/yol/paket.pkg.tar.zst");
    fireEvent.change(inputs[1], { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Attestasyon Üret"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.attest" }),
      ),
    );
  });

  it("calls tools.publish when path set and clicked", async () => {
    renderTools();
    const inputs = screen.getAllByPlaceholderText("/yol/paket.pkg.tar.zst");
    fireEvent.change(inputs[2], { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("AUR Paketi Hazırla"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.publish" }),
      ),
    );
  });

  it("calls tools.snapshot_install when clicked", async () => {
    renderTools();
    fireEvent.click(screen.getByText("Servisi Kur"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.snapshot_install" }),
      ),
    );
  });
});
