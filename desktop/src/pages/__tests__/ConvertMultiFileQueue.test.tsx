import { render, screen, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
type Handler = (evt: { payload: unknown }) => void;
const handlers = new Map<string, Handler[]>();

vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: (name: string, cb: Handler) => {
    const list = handlers.get(name) ?? [];
    list.push(cb);
    handlers.set(name, list);
    return Promise.resolve(() => {});
  },
}));

import { Convert } from "../Convert";
import { ToastProvider } from "../../components/ui/Toast";

type RpcReq = { id?: number; method?: string; params?: { path?: string } };

const FILES = ["/tmp/bir.deb", "/tmp/iki.deb", "/tmp/uc.deb"];

function rpcOk(id?: number) {
  return { jsonrpc: "2.0", id: id ?? 1, result: { ok: true }, error: null };
}

function startedPaths(): (string | undefined)[] {
  return invokeMock.mock.calls
    .map((c) => c[1] as RpcReq)
    .filter((r) => r?.method === "pipeline.start")
    .map((r) => r?.params?.path);
}

function emit(name: string, payload: unknown) {
  act(() => {
    for (const cb of handlers.get(name) ?? []) cb({ payload });
  });
}

beforeEach(() => {
  handlers.clear();
  invokeMock.mockReset();
  invokeMock.mockImplementation((cmd: string, req: RpcReq) =>
    Promise.resolve(cmd === "initial_files" ? FILES : rpcOk(req?.id)),
  );
});

describe("birden fazla dosyayla açılış", () => {
  it("her dosya sırayla dönüştürülür, hiçbiri düşmez", async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <Convert />
        </ToastProvider>,
      );
    });

    // Üçü de kuyrukta görünüyor mu?
    await vi.waitFor(() => expect(startedPaths().length).toBeGreaterThan(0));
    for (const f of FILES) {
      expect(
        screen.getByText(f.split("/").pop() as string),
      ).toBeInTheDocument();
    }

    // Ilk bitti -> ikinci başlamalı, ikinci bitti -> ucuncu.
    emit("event/finished", { success: true, message: "ok", output_pkg: "a.pkg.tar.zst" });
    await vi.waitFor(() => expect(startedPaths()).toHaveLength(2));
    emit("event/finished", { success: true, message: "ok", output_pkg: "b.pkg.tar.zst" });
    await vi.waitFor(() => expect(startedPaths()).toHaveLength(3));

    expect(startedPaths()).toEqual(FILES);
  });

  it("bir dosya başarısız olursa kuyruk devam eder", async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <Convert />
        </ToastProvider>,
      );
    });
    await vi.waitFor(() => expect(startedPaths().length).toBeGreaterThan(0));

    emit("event/finished", { success: false, message: "bozuk", output_pkg: null });
    await vi.waitFor(() => expect(startedPaths()).toHaveLength(2));
    emit("event/finished", { success: true, message: "ok", output_pkg: "b.pkg.tar.zst" });
    await vi.waitFor(() => expect(startedPaths()).toHaveLength(3));
    expect(startedPaths()).toEqual(FILES);
  });
});
