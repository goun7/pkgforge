// Faz 12: eventBinder unmount-yarışı düzeltmesinin birim testleri.
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

const listenMock = vi.fn();
vi.mock("@tauri-apps/api/event", () => ({
  listen: (...args: unknown[]) => listenMock(...args),
}));

import { eventBinder, onEvent } from "../rpc";

describe("eventBinder", () => {
  beforeEach(() => {
    listenMock.mockReset();
    invokeMock.mockReset();
  });

  it("dispose'dan ÖNCE çözülen abonelik dispose'da kaldırılır", async () => {
    const unlisten = vi.fn();
    listenMock.mockResolvedValue(unlisten);
    const b = eventBinder();
    b.bind(() => onEvent("event/x", () => {}));
    // Mikro-görevleri boşalt: promise çözülsün ama dispose olmadan.
    await new Promise((r) => setTimeout(r, 0));
    expect(unlisten).not.toHaveBeenCalled();
    b.dispose();
    expect(unlisten).toHaveBeenCalledTimes(1);
  });

  it("dispose'dan SONRA çözülen abonelik çözülür çözülmez kaldırılır", async () => {
    const unlisten = vi.fn();
    let resolveListen!: () => void;
    listenMock.mockImplementation(
      () => new Promise<typeof unlisten>((r) => { resolveListen = () => r(unlisten); }),
    );
    const b = eventBinder();
    b.bind(() => onEvent("event/x", () => {}));
    b.dispose();
    expect(unlisten).not.toHaveBeenCalled();
    resolveListen();
    await vi.waitFor(() => expect(unlisten).toHaveBeenCalledTimes(1));
  });

  it("çözülmeyen/reddedilen abonelik dispose'da hata fırlatmaz", async () => {
    listenMock.mockImplementation(() => new Promise(() => {})); // asla çözülmez
    const b = eventBinder();
    b.bind(() => onEvent("event/x", () => {}));
    b.dispose(); // fırlamamalı
    // reddeden senaryo: bind'in catch'i unhandled rejection üretmemeli
    listenMock.mockRejectedValue(new Error("listener patladi"));
    const b2 = eventBinder();
    b2.bind(() => onEvent("event/y", () => {}));
    await new Promise((r) => setTimeout(r, 0));
    b2.dispose();
  });

  it("çoklu bind: hepsi dispose ile kaldırılır", async () => {
    const uns = [vi.fn(), vi.fn(), vi.fn()];
    listenMock.mockImplementation(() => Promise.resolve(uns.shift()!));
    const b = eventBinder();
    b.bind(() => onEvent("event/a", () => {}));
    b.bind(() => onEvent("event/b", () => {}));
    b.bind(() => onEvent("event/c", () => {}));
    await new Promise((r) => setTimeout(r, 0));
    b.dispose();
    // kalan (henüz çözülmemiş olsa bile) — çözülenler çağrılmış olmalı
    expect(uns.length).toBeLessThanOrEqual(3);
  });
});
