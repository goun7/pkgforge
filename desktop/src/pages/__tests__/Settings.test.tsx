import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Settings } from "../Settings";
import { ToastProvider } from "../../components/ui/Toast";

function renderSettings() {
  return render(
    <ToastProvider>
      <Settings />
    </ToastProvider>,
  );
}

describe("Settings page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("loads and displays settings", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: { language: "tr", theme: "dark", clamav_scan: true, dry_run: false },
    });
    renderSettings();
    await vi.waitFor(() =>
      expect(screen.getByText("ClamAV malware taraması")).toBeInTheDocument(),
    );
    const clamav = screen.getByLabelText(/ClamAV malware taraması/) as HTMLInputElement;
    expect(clamav.checked).toBe(true);
  });

  it("saves settings via settings.set", async () => {
    invokeMock
      .mockResolvedValueOnce({ jsonrpc: "2.0", id: 1, result: { dry_run: false } })
      .mockResolvedValueOnce({ jsonrpc: "2.0", id: 2, result: { ok: true } });
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("Kaydet")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Kaydet"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "settings.set" }),
      ),
    );
  });

  it("toggles a boolean setting", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { dry_run: false } });
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("Kuru çalıştırma (dry-run)")).toBeInTheDocument());
    const dryRun = screen.getByLabelText(/Kuru çalıştırma/) as HTMLInputElement;
    expect(dryRun.checked).toBe(false);
    fireEvent.click(dryRun);
    expect(dryRun.checked).toBe(true);
  });

  it("renders the profile list (C2)", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      Promise.resolve({
        jsonrpc: "2.0",
        id: 1,
        result:
          payload.method === "profile.list"
            ? [
                { name: "default", active: true },
                { name: "work", active: false },
              ]
            : {},
      }),
    );
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("Profiller")).toBeInTheDocument());
    expect(screen.getByText("default")).toBeInTheDocument();
    expect(screen.getByText("work")).toBeInTheDocument();
  });

  it("creates a profile via profile.create", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      Promise.resolve({
        jsonrpc: "2.0",
        id: 1,
        result:
          payload.method === "profile.list"
            ? [{ name: "default", active: true }]
            : { name: "deneme" },
      }),
    );
    renderSettings();
    await vi.waitFor(() => expect(screen.getByPlaceholderText("Yeni profil adı…")).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText("Yeni profil adı…"), {
      target: { value: "deneme" },
    });
    fireEvent.click(screen.getByText("Oluştur"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "profile.create" }),
      ),
    );
  });

  it("switches profile via radio and profile.switch", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      Promise.resolve({
        jsonrpc: "2.0",
        id: 1,
        result:
          payload.method === "profile.list"
            ? [
                { name: "default", active: true },
                { name: "work", active: false },
              ]
            : { name: "work" },
      }),
    );
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("work")).toBeInTheDocument());
    const radio = screen.getByLabelText(/work/) as HTMLInputElement;
    fireEvent.click(radio);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "profile.switch" }),
      ),
    );
  });
});
