import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

import { TopbarActions } from "../TopbarActions";
import { setLang } from "../../lib/lang";

describe("TopbarActions — Faz 19 kapsam dalları", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ result: {}, error: null });
    // Her test bilinen tr dilinde başlar (lang store'u testler arası kalıcı).
    setLang("tr");
  });

  it("sidecar ping başarısızsa 'bağlı değil' göstergesi çıkar", async () => {
    invokeMock.mockRejectedValue(new Error("rpc yok"));
    render(<TopbarActions />);
    expect(
      await screen.findByLabelText("Sidecar bağlı değil"),
    ).toBeInTheDocument();
  });

  it("dil butonu canlı store'u en'ye çevirir ve settings.set çağırır", async () => {
    render(<TopbarActions />);
    const btn = await screen.findByLabelText("Dili değiştir");
    fireEvent.click(btn);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "settings.set",
          params: expect.objectContaining({ language: "en" }),
        }),
      ),
    );
    // Canlı store değişti — aria-label EN metnine döner (Change language).
    expect(await screen.findByLabelText("Change language")).toBeInTheDocument();
  });

  it("tema butonu data-theme günceller; settings.set çağrılır", async () => {
    render(<TopbarActions />);
    const themeBtn = await screen.findByLabelText("Temayı değiştir");
    fireEvent.click(themeBtn);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "settings.set",
          params: expect.objectContaining({ theme: expect.any(String) }),
        }),
      ),
    );
    expect(document.documentElement.getAttribute("data-theme")).toMatch(
      /light|dark|oled/,
    );
  });

  it("kısayol butonu pkgforge:open-shortcuts olayını yayınlar", async () => {
    const heard = vi.fn();
    window.addEventListener("pkgforge:open-shortcuts", heard);
    render(<TopbarActions />);
    fireEvent.click(await screen.findByLabelText("Klavye Kısayolları"));
    expect(heard).toHaveBeenCalledTimes(1);
    window.removeEventListener("pkgforge:open-shortcuts", heard);
  });

  it("settings.set hata verse bile dil canlı store'da değişir", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) =>
      payload.method === "settings.get"
        ? Promise.resolve({ result: {}, error: null })
        : Promise.reject(new Error("sidecar yok")),
    );
    render(<TopbarActions />);
    fireEvent.click(await screen.findByLabelText("Dili değiştir"));
    // RPC reddetti ama canlı store yeni dili aldı.
    expect(await screen.findByLabelText("Change language")).toBeInTheDocument();
  });
});
