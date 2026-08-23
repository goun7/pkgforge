import { render, screen, fireEvent } from "@testing-library/react";
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

import { Security } from "../Security";
import { ToastProvider } from "../../components/ui/Toast";

function renderSecurity() {
  return render(
    <ToastProvider>
      <Security />
    </ToastProvider>,
  );
}

describe("Security page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("renders all six tabs", () => {
    renderSecurity();
    expect(screen.getByText("İmza")).toBeInTheDocument();
    expect(screen.getByText("SBOM")).toBeInTheDocument();
    expect(screen.getByText("Kalite")).toBeInTheDocument();
    expect(screen.getByText("Provenance")).toBeInTheDocument();
    expect(screen.getByText("Sigstore")).toBeInTheDocument();
    expect(screen.getByText("CVE Tara")).toBeInTheDocument();
  });

  it("calls security.cve_scan when CVE tab used with a path", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { started: true } });
    renderSecurity();
    fireEvent.change(screen.getByPlaceholderText(/paket yolu/i), { target: { value: "/tmp/x.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("CVE Tara")); // open the tab
    fireEvent.click(screen.getByText("Taramayı Başlat")); // trigger the scan
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "security.cve_scan" }),
      ),
    );
  });

  it("has a package path input", () => {
    renderSecurity();
    expect(screen.getByPlaceholderText(/paket yolu/i)).toBeInTheDocument();
  });

  it("calls security.verify when verify clicked with a path", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: { signed: true, valid: true, key_id: "ABC", key_fingerprint: "fp", signer: "me", timestamp: "t", detail: "" },
    });
    renderSecurity();
    const input = screen.getByPlaceholderText(/paket yolu/i);
    fireEvent.change(input, { target: { value: "/tmp/x.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Doğrula"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "security.verify" }),
      ),
    );
  });

  it("shows signature result after verify", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: { signed: true, valid: true, key_id: "ABC123", key_fingerprint: "fp", signer: "tester", timestamp: "t", detail: "" },
    });
    renderSecurity();
    fireEvent.change(screen.getByPlaceholderText(/paket yolu/i), { target: { value: "/tmp/x.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Doğrula"));
    await vi.waitFor(() => expect(screen.getByText(/ABC123/)).toBeInTheDocument());
  });
});
