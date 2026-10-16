import { render, screen, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// Kabuk (Rust) tarafı argv'yi `initial_files` komutuyla expose eder; bu test
// o listenin Convert kuyruğuna kadar ulaştığını kanıtlar.
const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Convert } from "../Convert";
import { ToastProvider } from "../../components/ui/Toast";

type RpcReq = { id?: number; method?: string };

beforeEach(() => {
  invokeMock.mockReset();
  invokeMock.mockImplementation((cmd: string, req: RpcReq) => {
    if (cmd === "initial_files") {
      return Promise.resolve(["/tmp/argvdan-gelen.deb"]);
    }
    return Promise.resolve({
      jsonrpc: "2.0",
      id: req?.id ?? 1,
      result: { ok: true },
      error: null,
    });
  });
});

function startedConversions(): unknown[] {
  return invokeMock.mock.calls
    .map((c) => c[1] as RpcReq)
    .filter((r) => r?.method === "pipeline.start");
}

describe("kabuktan gelen paket dosyaları", () => {
  it("açılışta kuyruğa girer ve dönüştürmeyi başlatır", async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <Convert />
        </ToastProvider>,
      );
    });

    await vi.waitFor(() =>
      expect(screen.getByText("argvdan-gelen.deb")).toBeInTheDocument(),
    );
    await vi.waitFor(() => expect(startedConversions()).toHaveLength(1));
    const req = invokeMock.mock.calls.find(
      (c) => (c[1] as RpcReq)?.method === "pipeline.start",
    )?.[1] as { params?: { path?: string } };
    expect(req?.params?.path).toBe("/tmp/argvdan-gelen.deb");
  });

  it("komut yoksa (tarayıcı/headless) sessizce boş döner, sayfa açılır", async () => {
    invokeMock.mockImplementation((cmd: string) =>
      cmd === "initial_files"
        ? Promise.reject(new Error("No such command: initial_files"))
        : Promise.resolve({ jsonrpc: "2.0", id: 1, result: { ok: true }, error: null }),
    );
    await act(async () => {
      render(
        <ToastProvider>
          <Convert />
        </ToastProvider>,
      );
    });
    await vi.waitFor(() => expect(invokeMock).toHaveBeenCalled());
    expect(screen.queryByText("argvdan-gelen.deb")).not.toBeInTheDocument();
  });

  it("dizi olmayan yanıt kuyruğa girmez", async () => {
    invokeMock.mockImplementation((cmd: string, req: RpcReq) =>
      cmd === "initial_files"
        ? Promise.resolve({ unexpected: "shape" })
        : Promise.resolve({
            jsonrpc: "2.0",
            id: req?.id ?? 1,
            result: { ok: true },
            error: null,
          }),
    );
    await act(async () => {
      render(
        <ToastProvider>
          <Convert />
        </ToastProvider>,
      );
    });
    await vi.waitFor(() => expect(invokeMock).toHaveBeenCalled());
    expect(startedConversions()).toHaveLength(0);
  });
});
