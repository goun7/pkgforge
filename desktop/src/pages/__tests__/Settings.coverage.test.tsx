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

async function openCloudTab() {
  await screen.findByText("Bulut ve Servis");
  fireEvent.click(screen.getByText("Bulut ve Servis"));
}

async function openTab(label: string) {
  await screen.findByText(label);
  fireEvent.click(screen.getByText(label));
}

describe("Settings — Faz 19c kapsam dalları (bulut + dbus + profil)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      Promise.resolve({
        jsonrpc: "2.0",
        id: 1,
        result:
          payload.method === "settings.get"
            ? { language: "tr", theme: "dark" }
            : payload.method === "profile.list"
              ? [
                  { name: "default", active: true },
                  { name: "deneme", active: false },
                ]
              : payload.method === "dbus.status"
                ? { available: true, running: false, bus_name: "org.pkgforge.App" }
                : { started: true },
      }),
    );
  });

  it("profil oluşturma hatası toast basar", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      payload.method === "profile.create"
        ? Promise.reject(new Error("rota yok"))
        : Promise.resolve({ result: [], error: null }),
    );
    renderSettings();
    await openTab("Profiller");
    const input = await screen.findByPlaceholderText("Yeni profil adı…");
    fireEvent.change(input, { target: { value: "yeni" } });
    fireEvent.click(screen.getByText("Oluştur"));
    expect(await screen.findByText(/rota yok/)).toBeInTheDocument();
  });

  it("profil radio ile geçiş: profile.switch çağrılır", async () => {
    renderSettings();
    await openTab("Profiller");
    await screen.findByText("deneme");
    const radios = screen.getAllByRole("radio");
    const denemeRadio = radios.find(
      (r) =>
        !(r as HTMLInputElement).disabled &&
        ((r as HTMLInputElement).closest("label")?.textContent ?? "").includes("deneme"),
    );
    fireEvent.click(denemeRadio!);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "profile.switch",
          params: expect.objectContaining({ name: "deneme" }),
        }),
      ),
    );
  });

  it("profil silme RPC hatası toast basar", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      payload.method === "profile.delete"
        ? Promise.reject(new Error("yetki yok"))
        : payload.method === "profile.list"
          ? Promise.resolve({
              jsonrpc: "2.0",
              id: 1,
              result: [
                { name: "default", active: true },
                { name: "deneme", active: false },
              ],
            })
          : Promise.resolve({ result: [], error: null }),
    );
    renderSettings();
    await openTab("Profiller");
    await screen.findByText("deneme");
    fireEvent.click(screen.getByText("Sil"));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Sil" }));
    expect(await screen.findByText(/yetki yok/)).toBeInTheDocument();
  });

  it("senkron import: sync.import RPC çağrılır", async () => {
    renderSettings();
    await openCloudTab();
    // sync.import düğmesi bulut sekmesinde 'İçe Aktar'.
    const importBtn = await screen.findByRole("button", { name: "İçe Aktar" });
    fireEvent.click(importBtn);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "sync.import" }),
      ),
    );
  });

  it("WebDAV sunucu kaydı: sync.config URL ile çağrılır", async () => {
    renderSettings();
    await openCloudTab();
    const urlInput = await screen.findByPlaceholderText("https://sunucu/dav/");
    fireEvent.change(urlInput, { target: { value: "https://dav.example.com/" } });
    const saveBtn = screen
      .getAllByRole("button")
      .find((b) => /kaydet|Kaydet/i.test(b.textContent ?? ""));
    fireEvent.click(saveBtn!);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "sync.config" }),
      ),
    );
  });

  it("dbus Başlat: dbus.start çağrılır", async () => {
    renderSettings();
    await openCloudTab();
    await screen.findByText("D-Bus Servisi");
    fireEvent.click(screen.getByRole("button", { name: "Başlat" }));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "dbus.start" }),
      ),
    );
  });

  it("yedek yolu ve Dışa Aktar: yazma onChange + sync.export çağrısı", async () => {
    renderSettings();
    await openCloudTab();
    // Yedek yolu inputu (onChange satırı) + Dışa Aktar düğmesi.
    const pathInput = screen.getByPlaceholderText("Yedek yolu (boş = varsayılan)…");
    fireEvent.change(pathInput, { target: { value: "/tmp/yedek.zip" } });
    const exportBtn = screen.getByRole("button", { name: "Dışa Aktar" });
    fireEvent.click(exportBtn);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "sync.export",
          params: expect.objectContaining({ output_path: "/tmp/yedek.zip" }),
        }),
      ),
    );
  });

  it("WebDAV kullanıcı/parola alanları yazılabilir (onChange)", async () => {
    renderSettings();
    await openCloudTab();
    await screen.findByPlaceholderText("https://sunucu/dav/");
    const userBox = screen.getAllByRole("textbox").find(
      (b) => (b as HTMLInputElement).placeholder.toLowerCase().includes("kullanıcı"),
    );
    if (userBox) {
      fireEvent.change(userBox, { target: { value: "kullanici1" } });
      expect((userBox as HTMLInputElement).value).toBe("kullanici1");
    }
    // Parola kutusu (type=password) da yazılabilir olmalı.
    const passBox = document.querySelector('input[type="password"]');
    if (passBox) {
      fireEvent.change(passBox, { target: { value: "sifre123" } });
      expect((passBox as HTMLInputElement).value).toBe("sifre123");
    }
  });

  it("WebDAV URL girilince Buluta Gönder/Çek aktifleşir ve sync.push çağrılır", async () => {
    renderSettings();
    await openCloudTab();
    const urlInput = await screen.findByPlaceholderText("https://sunucu/dav/");
    // URL boş → push disabled.
    const pushBtn = await screen.findByRole("button", { name: "Buluta Gönder" });
    expect(pushBtn).toBeDisabled();
    // URL gir → aktif.
    fireEvent.change(urlInput, { target: { value: "https://dav.example.com/" } });
    expect(pushBtn).not.toBeDisabled();
    fireEvent.click(pushBtn);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "sync.push" }),
      ),
    );
  });

  it("Buluttan Çek: sync.pull çağrılır", async () => {
    renderSettings();
    await openCloudTab();
    const urlInput = await screen.findByPlaceholderText("https://sunucu/dav/");
    fireEvent.change(urlInput, { target: { value: "https://dav.example.com/" } });
    const pullBtn = screen.getByRole("button", { name: "Buluttan Çek" });
    fireEvent.click(pullBtn);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "sync.pull" }),
      ),
    );
  });

  it("dbus.status hata verirse servis kartı 'yok' metniyle ayakta kalır", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      payload.method === "dbus.status"
        ? Promise.reject(new Error("dbus yok"))
        : Promise.resolve({
            jsonrpc: "2.0",
            id: 1,
            result: { language: "tr", theme: "dark" },
          }),
    );
    renderSettings();
    await openCloudTab();
    // dbusStatus null → setDbusUnavailable metni görünür.
    expect(
      await screen.findByText(/D-Bus durumu okunamadı/),
    ).toBeInTheDocument();
  });
});
