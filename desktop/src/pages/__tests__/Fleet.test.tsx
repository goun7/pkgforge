import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { listen } from "@tauri-apps/api/event";
import { Fleet } from "../Fleet";
import { ToastProvider } from "../../components/ui/Toast";

/** The vi.fn installed by the vi.mock above, so tests can capture handlers. */
const listenMock = vi.mocked(listen);

const FLEET_STATUS = {
  backends: {
    webdav: { configured: true, available: true },
    git: { configured: false, available: true },
    "rclone-s3": { configured: false, available: false },
  },
  backend_names: ["webdav", "git", "rclone-s3"],
  age_available: true,
  profiles: ["default", "is"],
  sync_configured: true,
  history_count: 7,
  policy_level: "STRICT",
};

/** Degraded status: unknown backend name, no age, empty profiles, no sync. */
const FLEET_STATUS_DEGRADED = {
  backends: {},
  backend_names: ["ghost"],
  age_available: false,
  profiles: [],
  sync_configured: false,
  history_count: 0,
  policy_level: "RELAXED",
};

/** Wrap a result into a JSON-RPC success envelope. */
function rpcOk(result: unknown) {
  return { jsonrpc: "2.0", id: 1, result, error: null };
}

/** Build a JSON-RPC error envelope; call() rejects it as "code: message". */
function rpcErr(code: number, message: string) {
  return { jsonrpc: "2.0", id: 1, result: null, error: { code, message } };
}

/** Route rpc_call by method: fleet.status defaults to FLEET_STATUS,
 *  per-method overrides may be a full envelope or an Error to reject. */
function mockRpc(overrides: Record<string, unknown> = {}) {
  invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
    if (payload.method in overrides) {
      const v = overrides[payload.method];
      if (v instanceof Error) return Promise.reject(v);
      return Promise.resolve(v);
    }
    const result = payload.method === "fleet.status" ? FLEET_STATUS : { ok: true };
    return Promise.resolve({ jsonrpc: "2.0", id: 1, result });
  });
}

/** All rpc_call invocations aimed at a given method. */
function callsTo(method: string) {
  return invokeMock.mock.calls.filter(
    (c) => (c[1] as { method?: string } | undefined)?.method === method,
  );
}

type SyncDoneHandler = (e: { payload: { ok: boolean; error?: string } }) => void;

/** Capture the event/sync_done listener so a test can fire it. */
function captureSyncDone(): () => SyncDoneHandler | null {
  let handler: SyncDoneHandler | null = null;
  const impl = (_event: string, h: SyncDoneHandler) => {
    handler = h;
    return Promise.resolve(() => {});
  };
  listenMock.mockImplementationOnce(impl as unknown as typeof listen);
  return () => handler;
}

function renderFleet() {
  return render(
    <ToastProvider>
      <Fleet />
    </ToastProvider>,
  );
}

describe("Fleet page (Fleet konsolu)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: FLEET_STATUS });
  });

  it("loads fleet.status on mount", async () => {
    renderFleet();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "fleet.status" }),
      ),
    );
  });

  it("renders backend names and policy after load", async () => {
    renderFleet();
    await vi.waitFor(() =>
      expect(screen.getByText("webdav")).toBeInTheDocument(),
    );
    expect(screen.getByText("git")).toBeInTheDocument();
    expect(screen.getByText("rclone-s3")).toBeInTheDocument();
    expect(screen.getAllByText("STRICT").length).toBeGreaterThan(0);
  });

  it("shows profiles and history count", async () => {
    renderFleet();
    await vi.waitFor(() =>
      expect(screen.getByText(/default, is/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/7 geçmiş kayıt/)).toBeInTheDocument();
  });

  it("calls sync.push when Push clicked", async () => {
    renderFleet();
    fireEvent.click(screen.getByText("Push"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "sync.push" }),
      ),
    );
  });

  it("calls sync.export when Yedek Export clicked", async () => {
    renderFleet();
    fireEvent.click(screen.getByText("Yedek Export"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "sync.export" }),
      ),
    );
  });

  it("shows an error toast and keeps status cards hidden when fleet.status fails", async () => {
    mockRpc({ "fleet.status": rpcErr(-32000, "sidecar yanıt vermedi") });
    renderFleet();
    expect(await screen.findByText("-32000: sidecar yanıt vermedi")).toBeInTheDocument();
    // status null kaldi: backend/ozet kartlari render edilmez
    expect(screen.queryByText("Senkron Backend'leri")).not.toBeInTheDocument();
    expect(screen.queryByText("Durum Özeti")).not.toBeInTheDocument();
    expect(screen.queryByText(/geçmiş kayıt/)).not.toBeInTheDocument();
  });

  it("reloads fleet.status when Yenile clicked", async () => {
    renderFleet();
    await vi.waitFor(() => expect(screen.getByText("webdav")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Yenile" }));
    await vi.waitFor(() => expect(callsTo("fleet.status").length).toBe(2));
  });

  it("calls sync.pull when Pull clicked", async () => {
    renderFleet();
    fireEvent.click(screen.getByText("Pull"));
    await vi.waitFor(() => expect(callsTo("sync.pull").length).toBe(1));
  });

  it("shows an error toast and frees the button when sync.push fails", async () => {
    mockRpc({ "sync.push": rpcErr(-1, "push başarısız") });
    renderFleet();
    await vi.waitFor(() => expect(screen.getByText("webdav")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Push" }));
    expect(await screen.findByText("-1: push başarısız")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Push" })).not.toBeDisabled();
  });

  it("shows an error toast when sync.pull fails", async () => {
    mockRpc({ "sync.pull": rpcErr(-2, "pull başarısız") });
    renderFleet();
    await vi.waitFor(() => expect(screen.getByText("webdav")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Pull" }));
    expect(await screen.findByText("-2: pull başarısız")).toBeInTheDocument();
  });

  it("shows a success toast after sync.export succeeds", async () => {
    renderFleet();
    fireEvent.click(screen.getByText("Yedek Export"));
    expect(await screen.findByText("Yedek export tamamlandı")).toBeInTheDocument();
  });

  it("shows an error toast when sync.export fails", async () => {
    mockRpc({ "sync.export": rpcErr(-3, "export yazılamadı") });
    renderFleet();
    fireEvent.click(screen.getByText("Yedek Export"));
    expect(await screen.findByText("-3: export yazılamadı")).toBeInTheDocument();
    expect(screen.queryByText("Yedek export tamamlandı")).not.toBeInTheDocument();
  });

  it("sync_done ok event clears busy and shows success toast", async () => {
    const getHandler = captureSyncDone();
    renderFleet();
    await vi.waitFor(() => expect(screen.getByText("webdav")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Push" }));
    await vi.waitFor(() => expect(callsTo("sync.push").length).toBe(1));
    await vi.waitFor(() => expect(getHandler()).not.toBeNull());
    act(() => {
      getHandler()?.({ payload: { ok: true } });
    });
    expect(await screen.findByText("Senkron tamamlandı")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Push" })).not.toBeDisabled();
  });

  it("sync_done failure event shows the backend error", async () => {
    const getHandler = captureSyncDone();
    renderFleet();
    await vi.waitFor(() => expect(getHandler()).not.toBeNull());
    act(() => {
      getHandler()?.({ payload: { ok: false, error: "disk dolu" } });
    });
    expect(await screen.findByText("disk dolu")).toBeInTheDocument();
    expect(screen.queryByText("Senkron başarısız")).not.toBeInTheDocument();
  });

  it("sync_done failure without error text falls back to fleetSyncFail", async () => {
    const getHandler = captureSyncDone();
    renderFleet();
    await vi.waitFor(() => expect(getHandler()).not.toBeNull());
    act(() => {
      getHandler()?.({ payload: { ok: false } });
    });
    expect(await screen.findByText("Senkron başarısız")).toBeInTheDocument();
  });

  it("renders fallback badges for unknown backend and empty summary fields", async () => {
    mockRpc({ "fleet.status": rpcOk(FLEET_STATUS_DEGRADED) });
    renderFleet();
    await vi.waitFor(() => expect(screen.getByText("ghost")).toBeInTheDocument());
    // backends["ghost"] yok -> {configured:false, available:false} fallback
    expect(screen.getByText("YOK")).toBeInTheDocument();
    expect(screen.queryByText("yapılandırıldı")).not.toBeInTheDocument();
    // age yok
    expect(screen.getByText(/age şifreleme: yok/)).toBeInTheDocument();
    // bos profiller -> "-"
    expect(screen.getByText("Profiller:", { exact: false }).textContent).toBe("Profiller: -");
    // senkron yapilandirilmamis
    expect(screen.getByText("Senkron:", { exact: false }).textContent).toBe("Senkron: yok");
    // sifir gecmis yine de gosterilir
    expect(screen.getByText(/0 geçmiş kayıt/)).toBeInTheDocument();
    expect(screen.getAllByText("RELAXED").length).toBeGreaterThan(0);
  });
});
