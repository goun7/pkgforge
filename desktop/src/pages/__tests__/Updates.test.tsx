import { render, screen, fireEvent, act, within } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { listen } from "@tauri-apps/api/event";
import { Updates } from "../Updates";
import { ToastProvider } from "../../components/ui/Toast";

/** The vi.fn installed by the vi.mock above, so tests can capture handlers. */
const listenMock = vi.mocked(listen);

const DELTA = { installed: false, active: false, next_run: "" };
const SCHEDULE = { enabled: false, interval_hours: 24, task: "check_updates", last_run: "", next_run: "" };

/** Route rpc_call responses by method so both cards load cleanly. */
function mockByMethod() {
  invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
    const result =
      payload.method === "schedule.get" ? SCHEDULE :
      payload.method === "delta.status" ? DELTA :
      { ok: true };
    return Promise.resolve({ jsonrpc: "2.0", id: 1, result });
  });
}

const DELTA_ACTIVE = { installed: true, active: true, next_run: "2025-08-30 10:00" };
const DELTA_INSTALLED = { installed: true, active: false, next_run: "" };
const SCHEDULE_ON = {
  enabled: true,
  interval_hours: 12,
  task: "check_updates",
  last_run: "2025-08-29 09:00",
  next_run: "2025-08-30 09:00",
};
const CROSS = {
  package_name: "firefox",
  local_version: "120.0",
  aur_version: "121.0",
  flatpak_version: "",
  recommended_source: "aur",
  recommendation_reason: "AUR sürümü daha yeni",
};

/** Wrap a result into a JSON-RPC success envelope. */
function rpcOk(result: unknown) {
  return { jsonrpc: "2.0", id: 1, result, error: null };
}

/** Build a JSON-RPC error envelope; call() rejects it as "code: message". */
function rpcErr(code: number, message: string) {
  return { jsonrpc: "2.0", id: 1, result: null, error: { code, message } };
}

/** Route rpc_call by method like mockByMethod, with per-method overrides.
 *  An override may be a full envelope, or an Error to reject the invoke. */
function mockRpc(overrides: Record<string, unknown> = {}) {
  invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
    if (payload.method in overrides) {
      const v = overrides[payload.method];
      if (v instanceof Error) return Promise.reject(v);
      return Promise.resolve(v);
    }
    const result =
      payload.method === "schedule.get" ? SCHEDULE :
      payload.method === "delta.status" ? DELTA :
      { ok: true };
    return Promise.resolve({ jsonrpc: "2.0", id: 1, result });
  });
}

/** All rpc_call invocations aimed at a given method. */
function callsTo(method: string) {
  return invokeMock.mock.calls.filter(
    (c) => (c[1] as { method?: string } | undefined)?.method === method,
  );
}

type CrossDoneHandler = (e: { payload: unknown }) => void;

/** Capture the event/cross_check_done listener so a test can fire it. */
function captureCrossCheckDone(): () => CrossDoneHandler | null {
  let handler: CrossDoneHandler | null = null;
  const impl = (_event: string, h: CrossDoneHandler) => {
    handler = h;
    return Promise.resolve(() => {});
  };
  listenMock.mockImplementationOnce(impl as unknown as typeof listen);
  return () => handler;
}

/** Type a package name into the cross-check input. */
async function typePackageName(name: string) {
  const input = await screen.findByPlaceholderText(/paket adı/i);
  fireEvent.change(input, { target: { value: name } });
}

function renderUpdates() {
  return render(
    <ToastProvider>
      <Updates />
    </ToastProvider>,
  );
}

describe("Updates page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    mockByMethod();
  });

  it("loads delta status on mount", async () => {
    renderUpdates();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "delta.status" }),
      ),
    );
  });

  it("loads schedule state on mount", async () => {
    renderUpdates();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "schedule.get" }),
      ),
    );
  });

  it("shows the scheduled tasks card", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Devre dışı")).toBeInTheDocument());
    expect(screen.getByText("Zamanlanmış Görevler")).toBeInTheDocument();
  });

  it("toggles the schedule on", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Devre dışı")).toBeInTheDocument());
    // The schedule card's own enable button (second "Etkinleştir" on the page).
    const enableButtons = screen.getAllByText("Etkinleştir");
    fireEvent.click(enableButtons[enableButtons.length - 1]);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "schedule.set", params: expect.objectContaining({ enabled: true }) }),
      ),
    );
  });

  it("has a cross-check input", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByPlaceholderText(/paket adı/i)).toBeInTheDocument());
  });

  it("shows skeletons on both cards while initial data is pending", () => {
    // Keep both loads in flight so the loading branches stay visible.
    invokeMock.mockImplementation(() => new Promise((r) => setTimeout(r, 50)));
    const { container } = renderUpdates();
    expect(container.querySelectorAll(".animate-pulse").length).toBe(2);
  });

  it("renders an active delta with next run and locks the enable button", async () => {
    mockRpc({ "delta.status": rpcOk(DELTA_ACTIVE) });
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Zamanlayıcı kurulu")).toBeInTheDocument());
    expect(screen.getByText("Aktif")).toBeInTheDocument();
    expect(screen.getByText("Sonraki çalışma: 2025-08-30 10:00")).toBeInTheDocument();
    const enableButtons = screen.getAllByRole("button", { name: "Etkinleştir" });
    expect(enableButtons[0]).toBeDisabled(); // delta card: already active
    expect(enableButtons[1]).toBeEnabled(); // schedule card
    expect(screen.getAllByRole("button", { name: "Kapat" })[0]).toBeEnabled(); // installed
  });

  it("renders an inactive delta without next run and locks disable", async () => {
    renderUpdates(); // DELTA: not installed, not active, empty next_run
    await vi.waitFor(() =>
      expect(screen.getByText("Zamanlayıcı kurulu değil")).toBeInTheDocument(),
    );
    expect(screen.getByText("Pasif")).toBeInTheDocument();
    expect(screen.queryByText(/Sonraki çalışma:/)).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Kapat" })[0]).toBeDisabled(); // not installed
  });

  it("refresh button reloads the delta status", async () => {
    renderUpdates();
    await vi.waitFor(() =>
      expect(screen.getByText("Zamanlayıcı kurulu değil")).toBeInTheDocument(),
    );
    expect(callsTo("delta.status")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Yenile" }));
    await vi.waitFor(() => expect(callsTo("delta.status")).toHaveLength(2));
  });

  it("enable delta shows the backend privilege message and refreshes", async () => {
    mockRpc({ "delta.enable": rpcOk({ requires_privilege: true, message: "pkexec gerekli" }) });
    renderUpdates();
    await vi.waitFor(() =>
      expect(screen.getByText("Zamanlayıcı kurulu değil")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Etkinleştir" })[0]);
    await vi.waitFor(() => expect(callsTo("delta.enable")).toHaveLength(1));
    expect(await screen.findByText("pkexec gerekli")).toBeInTheDocument();
    await vi.waitFor(() => expect(callsTo("delta.status")).toHaveLength(2));
  });

  it("enable delta falls back to the default privilege toast without a message", async () => {
    mockRpc({ "delta.enable": rpcOk({ requires_privilege: true }) });
    renderUpdates();
    await vi.waitFor(() =>
      expect(screen.getByText("Zamanlayıcı kurulu değil")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Etkinleştir" })[0]);
    expect(
      await screen.findByText("Delta auto-update etkinleştirme yetkili işlem gerektiriyor (pkexec)"),
    ).toBeInTheDocument();
  });

  it("enable delta without privilege need only refreshes the status", async () => {
    mockRpc({ "delta.enable": rpcOk({}) });
    renderUpdates();
    await vi.waitFor(() =>
      expect(screen.getByText("Zamanlayıcı kurulu değil")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Etkinleştir" })[0]);
    await vi.waitFor(() => expect(callsTo("delta.status")).toHaveLength(2));
    expect(screen.queryByText(/yetkili işlem/)).not.toBeInTheDocument();
  });

  it("disable delta (confirmed) falls back to the default privilege toast without a message", async () => {
    mockRpc({
      "delta.status": rpcOk(DELTA_INSTALLED),
      "delta.disable": rpcOk({ requires_privilege: true }),
    });
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Zamanlayıcı kurulu")).toBeInTheDocument());
    // Faz 16: delta kartindaki 'Kapat' artik onay acar (ilk 'Kapat' = delta karti;
    // ikincisi zamanlanmis gorevler kartindaki).
    fireEvent.click(screen.getAllByText("Kapat")[0]);
    expect(callsTo("delta.disable")).toHaveLength(0);
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByText("Kapat"));
    await vi.waitFor(() => expect(callsTo("delta.disable")).toHaveLength(1));
    expect(
      await screen.findByText("Delta auto-update kapatma yetkili işlem gerektiriyor (pkexec)"),
    ).toBeInTheDocument();
  });

  it("disable delta without privilege only refreshes the status", async () => {
    mockRpc({ "delta.status": rpcOk(DELTA_INSTALLED), "delta.disable": rpcOk({}) });
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Zamanlayıcı kurulu")).toBeInTheDocument());
    fireEvent.click(screen.getAllByText("Kapat")[0]);
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByText("Kapat"));
    await vi.waitFor(() => expect(callsTo("delta.status")).toHaveLength(2));
    expect(screen.queryByText(/yetkili işlem/)).not.toBeInTheDocument();
  });

  it("shows an error toast when delta.enable fails", async () => {
    mockRpc({ "delta.enable": rpcErr(-32601, "delta etkinlestirilemedi") });
    renderUpdates();
    await vi.waitFor(() =>
      expect(screen.getByText("Zamanlayıcı kurulu değil")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Etkinleştir" })[0]);
    expect(await screen.findByText("-32601: delta etkinlestirilemedi")).toBeInTheDocument();
  });

  it("delta status error leaves the delta card empty and shows a toast", async () => {
    mockRpc({ "delta.status": rpcErr(-32000, "delta durumu okunamadi") });
    renderUpdates();
    expect(await screen.findByText("-32000: delta durumu okunamadi")).toBeInTheDocument();
    expect(screen.queryByText("Zamanlayıcı kurulu değil")).not.toBeInTheDocument();
    expect(screen.queryByText("Zamanlayıcı kurulu")).not.toBeInTheDocument();
  });

  it("renders an enabled schedule with next/last run and the saved interval", async () => {
    mockRpc({ "schedule.get": rpcOk(SCHEDULE_ON) });
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Etkin")).toBeInTheDocument());
    expect(screen.getByText("Sonraki: 2025-08-30 09:00")).toBeInTheDocument();
    expect(screen.getByText("Son çalışma: 2025-08-29 09:00")).toBeInTheDocument();
    expect(screen.getByRole("spinbutton")).toHaveValue(12);
    expect(screen.getAllByRole("button", { name: "Etkinleştir" })[1]).toBeDisabled();
    expect(screen.getAllByRole("button", { name: "Kapat" })[1]).toBeEnabled();
  });

  it("saves a valid interval", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Devre dışı")).toBeInTheDocument());
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "Kaydet" }));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "schedule.set", params: { interval_hours: 12 } }),
      ),
    );
  });

  it("rejects an interval below one hour without calling the backend", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Devre dışı")).toBeInTheDocument());
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "0.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Aralık en az 1 saat olmalı")).toBeInTheDocument();
    expect(callsTo("schedule.set")).toHaveLength(0);
  });

  it("rejects a non-numeric interval without calling the backend", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Devre dışı")).toBeInTheDocument());
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Aralık en az 1 saat olmalı")).toBeInTheDocument();
    expect(callsTo("schedule.set")).toHaveLength(0);
  });

  it("disables an enabled schedule", async () => {
    mockRpc({ "schedule.get": rpcOk(SCHEDULE_ON) });
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Etkin")).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole("button", { name: "Kapat" })[1]);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "schedule.set",
          params: expect.objectContaining({ enabled: false }),
        }),
      ),
    );
  });

  it("run now triggers schedule.run and shows a success toast", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Devre dışı")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Şimdi çalıştır" }));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "schedule.run", params: { force: true } }),
      ),
    );
    expect(await screen.findByText("Zamanlanmış görevler çalıştırıldı")).toBeInTheDocument();
    await vi.waitFor(() => expect(callsTo("schedule.get").length).toBeGreaterThanOrEqual(2));
  });

  it("shows an error toast when schedule.run fails", async () => {
    mockRpc({ "schedule.run": rpcErr(-1, "görev çalıştırılamadı") });
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Devre dışı")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Şimdi çalıştır" }));
    expect(await screen.findByText("-1: görev çalıştırılamadı")).toBeInTheDocument();
    expect(screen.queryByText("Zamanlanmış görevler çalıştırıldı")).not.toBeInTheDocument();
  });

  it("shows an error toast when the schedule toggle fails", async () => {
    mockRpc({ "schedule.set": rpcErr(-2, "zamanlama değiştirilemedi") });
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByText("Devre dışı")).toBeInTheDocument());
    const enableButtons = screen.getAllByRole("button", { name: "Etkinleştir" });
    fireEvent.click(enableButtons[enableButtons.length - 1]);
    expect(await screen.findByText("-2: zamanlama değiştirilemedi")).toBeInTheDocument();
  });

  it("schedule load error keeps the schedule card as a skeleton", async () => {
    mockRpc({ "schedule.get": rpcErr(-3, "zamanlama okunamadı") });
    const { container } = renderUpdates();
    expect(await screen.findByText("-3: zamanlama okunamadı")).toBeInTheDocument();
    expect(screen.getByText("Zamanlayıcı kurulu değil")).toBeInTheDocument(); // delta loaded
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Şimdi çalıştır")).not.toBeInTheDocument();
  });

  it("empty package name warns and skips the cross-check call", async () => {
    renderUpdates();
    await vi.waitFor(() => expect(screen.getByPlaceholderText(/paket adı/i)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Karşılaştır" }));
    expect(await screen.findByText("Bir paket adı girin")).toBeInTheDocument();
    expect(callsTo("system.cross_check")).toHaveLength(0);
  });

  it("compare renders the version table after a successful cross_check_done event", async () => {
    const getHandler = captureCrossCheckDone();
    const { container } = renderUpdates();
    await typePackageName("firefox");
    fireEvent.click(screen.getByRole("button", { name: "Karşılaştır" }));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "system.cross_check",
          params: { package_name: "firefox" },
        }),
      ),
    );
    // While the event is pending: button disabled and checking skeleton shown.
    expect(screen.getByRole("button", { name: "Karşılaştır" })).toBeDisabled();
    expect(container.querySelector(".h-20")).not.toBeNull();
    const handler = getHandler();
    expect(handler).not.toBeNull();
    act(() => {
      handler?.({ payload: { ok: true, result: CROSS } });
    });
    expect(await screen.findByText("Yerel")).toBeInTheDocument();
    expect(screen.getByText("120.0")).toBeInTheDocument();
    expect(screen.getByText("121.0")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument(); // flatpak version missing
    expect(screen.getByText("Öneri: aur")).toBeInTheDocument();
    expect(screen.getByText("AUR sürümü daha yeni")).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(screen.getByRole("button", { name: "Karşılaştır" })).toBeEnabled(),
    );
    expect(container.querySelector(".h-20")).toBeNull();
  });

  it("compare shows the fallback toast when the event carries no result", async () => {
    const getHandler = captureCrossCheckDone();
    renderUpdates();
    await typePackageName("firefox");
    fireEvent.click(screen.getByRole("button", { name: "Karşılaştır" }));
    await vi.waitFor(() => expect(callsTo("system.cross_check")).toHaveLength(1));
    act(() => {
      getHandler()?.({ payload: { ok: true } }); // ok but no result
    });
    expect(await screen.findByText("Cross-check başarısız")).toBeInTheDocument();
    expect(screen.queryByText("Yerel")).not.toBeInTheDocument();
    await vi.waitFor(() =>
      expect(screen.getByRole("button", { name: "Karşılaştır" })).toBeEnabled(),
    );
  });

  it("compare surfaces the event error message when one is provided", async () => {
    const getHandler = captureCrossCheckDone();
    renderUpdates();
    await typePackageName("firefox");
    fireEvent.click(screen.getByRole("button", { name: "Karşılaştır" }));
    await vi.waitFor(() => expect(callsTo("system.cross_check")).toHaveLength(1));
    act(() => {
      getHandler()?.({ payload: { ok: false, error: "AUR sorgusu patladı" } });
    });
    expect(await screen.findByText("AUR sorgusu patladı")).toBeInTheDocument();
    expect(screen.queryByText("Cross-check başarısız")).not.toBeInTheDocument();
  });

  it("compare call rejection re-enables the button and shows an error toast", async () => {
    captureCrossCheckDone();
    mockRpc({ "system.cross_check": new Error("sidecar koptu") });
    renderUpdates();
    await typePackageName("firefox");
    fireEvent.click(screen.getByRole("button", { name: "Karşılaştır" }));
    expect(await screen.findByText("sidecar koptu")).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(screen.getByRole("button", { name: "Karşılaştır" })).toBeEnabled(),
    );
    expect(screen.queryByText("Yerel")).not.toBeInTheDocument();
  });

  it("compare renders dashes for all missing versions and no reason line", async () => {
    const getHandler = captureCrossCheckDone();
    const { container } = renderUpdates();
    await typePackageName("vim");
    fireEvent.click(screen.getByRole("button", { name: "Karşılaştır" }));
    await vi.waitFor(() => expect(callsTo("system.cross_check")).toHaveLength(1));
    act(() => {
      getHandler()?.({
        payload: {
          ok: true,
          result: {
            package_name: "vim",
            local_version: "",
            aur_version: "",
            flatpak_version: "",
            recommended_source: "flatpak",
            recommendation_reason: "",
          },
        },
      });
    });
    await vi.waitFor(() => expect(screen.getAllByText("—")).toHaveLength(3));
    expect(screen.getByText("Öneri: flatpak")).toBeInTheDocument();
    expect(container.querySelector("p.mt-1")).toBeNull(); // no recommendation reason
  });
});
