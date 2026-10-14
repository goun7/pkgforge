/** Tauri IPC'suz ortamda RPC hatasinin kullaniciya nasil yansidigini kilitler.
 *
 * Headless görsel turda (ve tarayıcıda `vite` ile açıldığında) Ayarlar sayfası
 * sağ altta "Cannot read properties of undefined (reading 'invoke')" toast'ı
 * gösteriyordu: @tauri-apps/api/core'un invoke'u window.__TAURI__ yokken ham
 * TypeError atıyor, arayüz bu mesajı doğrudan basıyordu. Kullanıcı neyin eksik
 * olduğunu anlamıyor. Artık tek yerde, anlaşılan bir sebeple değiştiriliyor.
 */
import { describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { call, tauriYoksaAcikla } from "../rpc";

/** @tauri-apps/api/core'un IPC'siz ortamda ürettiği hatanın aynısı. */
function tauriYokTypeError(): TypeError {
  return new TypeError("Cannot read properties of undefined (reading 'invoke')");
}

describe("tauriYoksaAcikla", () => {
  it("Tauri köprüsü yoksa ham TypeError yerine anlaşılır sebep döner", () => {
    const hata = tauriYoksaAcikla(tauriYokTypeError()) as Error;
    expect(hata).toBeInstanceOf(Error);
    expect(hata.message).not.toMatch(/Cannot read properties/);
    expect(hata.message.length).toBeGreaterThan(10);
  });

  it("gerçek RPC hatalarına dokunmaz", () => {
    const zamanAsimi = new Error("rpcTimeout: convert");
    expect(tauriYoksaAcikla(zamanAsimi)).toBe(zamanAsimi);
    const tipHatasi = new TypeError("x.y is not a function");
    expect(tauriYoksaAcikla(tipHatasi)).toBe(tipHatasi);
    expect(tauriYoksaAcikla("string hata")).toBe("string hata");
  });
});

describe("call() Tauri olmadan", () => {
  it("invoke ham TypeError atarsa kullanıcı net mesaj görür", async () => {
    invokeMock.mockReset();
    invokeMock.mockImplementation(() => {
      throw tauriYokTypeError();
    });
    await expect(call("settings.get")).rejects.toThrow(/Masaüstü köprüsü yok/);
  });

  it("başka bir hata aynen yukarı gider", async () => {
    invokeMock.mockReset();
    invokeMock.mockRejectedValue(new Error("sidecar göçtü"));
    await expect(call("settings.get")).rejects.toThrow("sidecar göçtü");
  });
});
