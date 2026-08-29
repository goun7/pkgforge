import { render, screen, fireEvent, within } from "@testing-library/react";
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
    fireEvent.click(screen.getByText("Profiller")); // Faz 7: profil sekmesi
    await vi.waitFor(() => expect(screen.getByText("default")).toBeInTheDocument());
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
    await vi.waitFor(() => expect(screen.getByText("Profiller")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Profiller")); // Faz 7: profil sekmesi
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
    await vi.waitFor(() => expect(screen.getByText("Profiller")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Profiller")); // Faz 7: profil sekmesi
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

  it("exports a local backup via sync.export (C3)", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      Promise.resolve({
        jsonrpc: "2.0",
        id: 1,
        result:
          payload.method === "profile.list"
            ? [{ name: "default", active: true }]
            : payload.method === "sync.export"
              ? { ok: true, path: "/tmp/b.zip", size: 10 }
              : {},
      }),
    );
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("Bulut ve Servis")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Bulut ve Servis")); // Faz 7: bulut sekmesi
    await vi.waitFor(() => expect(screen.getByText("Dışa Aktar")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Dışa Aktar"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "sync.export" }),
      ),
    );
  });

  it("saves WebDAV server via sync.config", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      Promise.resolve({
        jsonrpc: "2.0",
        id: 1,
        result:
          payload.method === "profile.list" ? [{ name: "default", active: true }] : { ok: true },
      }),
    );
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("Bulut ve Servis")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Bulut ve Servis")); // Faz 7: bulut sekmesi
    await vi.waitFor(() => expect(screen.getByText("Sunucuyu Kaydet")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Sunucuyu Kaydet"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "sync.config" }),
      ),
    );
  });

  it("renders D-Bus status card (C1)", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      Promise.resolve({
        jsonrpc: "2.0",
        id: 1,
        result:
          payload.method === "dbus.status"
            ? { available: true, running: false, bus_name: "org.pkgforge.App" }
            : payload.method === "profile.list"
              ? [{ name: "default", active: true }]
              : {},
      }),
    );
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("Bulut ve Servis")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Bulut ve Servis")); // Faz 7: bulut sekmesi
    await vi.waitFor(() => expect(screen.getByText("D-Bus Servisi")).toBeInTheDocument());
    expect(screen.getByText("org.pkgforge.App")).toBeInTheDocument();
    expect(screen.getByText("Kapalı")).toBeInTheDocument();
  });

  it("starts the D-Bus service via dbus.start", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      Promise.resolve({
        jsonrpc: "2.0",
        id: 1,
        result:
          payload.method === "dbus.status"
            ? { available: true, running: false, bus_name: "org.pkgforge.App" }
            : payload.method === "profile.list"
              ? [{ name: "default", active: true }]
              : { started: true },
      }),
    );
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("Bulut ve Servis")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Bulut ve Servis")); // Faz 7: bulut sekmesi
    await vi.waitFor(() => expect(screen.getByText("Başlat")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Başlat"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "dbus.start" }),
      ),
    );
  });
});

describe("Settings — Faz 15 (onaylı profil silme + kirli göstergesi)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  const profilesPayload = (_cmd: string, payload: { method: string }) =>
    Promise.resolve({
      jsonrpc: "2.0",
      id: 1,
      result:
        payload.method === "profile.list"
          ? [
              { name: "default", active: true },
              { name: "deneme", active: false },
            ]
          : { started: true },
    });

  it("profil silme onay dialogu açılır; Vazgeç RPC çağırmaz", async () => {
    invokeMock.mockImplementation(profilesPayload);
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("Profiller")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Profiller")); // profiller sekmesi
    await vi.waitFor(() => expect(screen.getByText("deneme")).toBeInTheDocument());
    // Satırdaki Sil (tek, "deneme" satırında).
    fireEvent.click(screen.getByText("Sil"));
    // Onay penceresi açılır — henüz profile.delete çağrılmadı.
    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog).getByText(/kalıcı olarak silinecek/),
    ).toBeInTheDocument();
    expect(
      invokeMock.mock.calls.some((c) => c[1]?.method === "profile.delete"),
    ).toBe(false);
    fireEvent.click(within(dialog).getByText("Vazgeç"));
    await vi.waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(
      invokeMock.mock.calls.some((c) => c[1]?.method === "profile.delete"),
    ).toBe(false);
  });

  it("onaydan sonra profile.delete çağrılır", async () => {
    invokeMock.mockImplementation(profilesPayload);
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("Profiller")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Profiller"));
    await vi.waitFor(() => expect(screen.getByText("deneme")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Sil"));
    const dialog = screen.getByRole("dialog");
    // Onay: dialog icindeki gercek buton (baslik h2 de "Sil" iceriyor).
    fireEvent.click(within(dialog).getByRole("button", { name: "Sil" }));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "profile.delete" }),
      ),
    );
    expect(
      invokeMock.mock.calls.some(
        (c) => c[1]?.method === "profile.delete" && c[1]?.params?.name === "deneme",
      ),
    ).toBe(true);
  });

  it("değişiklik yapılmadan kaydet göstergesi çıkmaz; değişince çıkar, kaydedince gider", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      Promise.resolve({
        jsonrpc: "2.0",
        id: 1,
        result:
          payload.method === "settings.get"
            ? { language: "tr", theme: "dark" }
            : payload.method === "profile.list"
              ? [{ name: "default", active: true }]
              : { started: true },
      }),
    );
    renderSettings();
    await vi.waitFor(() => expect(screen.getByText("Kaydet")).toBeInTheDocument());
    expect(screen.queryByText("Kaydedilmemiş değişiklikler var")).not.toBeInTheDocument();
    // Tema secenegini degistir
    const themeSelect = screen.getAllByRole("combobox")[1] as HTMLSelectElement;
    fireEvent.change(themeSelect, { target: { value: "light" } });
    expect(screen.getByText("Kaydedilmemiş değişiklikler var")).toBeInTheDocument();
    // Kaydet -> gosterigi kaldir
    fireEvent.click(screen.getByText("Kaydet"));
    await vi.waitFor(() =>
      expect(screen.queryByText("Kaydedilmemiş değişiklikler var")).not.toBeInTheDocument(),
    );
  });
});
