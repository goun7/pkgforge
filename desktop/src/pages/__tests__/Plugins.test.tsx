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
import { Plugins } from "../Plugins";
import { ToastProvider } from "../../components/ui/Toast";

function renderPlugins() {
  return render(
    <ToastProvider>
      <Plugins />
    </ToastProvider>,
  );
}

describe("Plugins page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: [] });
  });

  it("renders installed and available tabs", async () => {
    renderPlugins();
    await vi.waitFor(() => expect(screen.getByText(/Kurulu/)).toBeInTheDocument());
    expect(screen.getByText(/Kullanılabilir/)).toBeInTheDocument();
  });

  it("loads installed plugins on mount", async () => {
    renderPlugins();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "plugin.list" }),
      ),
    );
  });

  it("shows empty message when no installed plugins", async () => {
    renderPlugins();
    await vi.waitFor(() =>
      expect(screen.getByText(/yerel plugin yok/i)).toBeInTheDocument(),
    );
  });
});

const INSTALLED = [{ name: "plasmoid-x", path: "/opt/plasmoid-x", size: "120" }];
const AVAILABLE = [
  {
    name: "pkg-browser",
    version: "1.2.0",
    description: "Paket gezgini",
    download_url: "https://example.com/pkg-browser.zip",
    sha256_url: "https://example.com/pkg-browser.zip.sha256",
  },
];
const AUDITS = [
  { name: "plasmoid-x", status: "ok", message: "saglam" },
  { name: "eski-eklenti", status: "bozuk", message: "imza hatasi" },
];

/** Route rpc_call responses by method; optionally fail selected methods. */
function mockRpc(
  results: Record<string, unknown> = {},
  errors: Record<string, { code: number; message: string }> = {},
) {
  invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
    const error = errors[payload.method];
    if (error) {
      return Promise.resolve({ jsonrpc: "2.0", id: 1, result: null, error });
    }
    const result = payload.method in results ? results[payload.method] : [];
    return Promise.resolve({ jsonrpc: "2.0", id: 1, result, error: null });
  });
}

function callsFor(method: string) {
  return invokeMock.mock.calls.filter(
    (c) => (c[1] as { method?: string } | undefined)?.method === method,
  );
}

type PluginDonePayload = {
  ok: boolean;
  result?: { ok?: boolean; message?: string };
  error?: string;
};

/** Capture the event/plugin_done listener the page registers via listen(). */
function capturePluginDoneHandler() {
  let handler: ((e: { payload: PluginDonePayload }) => void) | undefined;
  vi.mocked(listen).mockImplementationOnce(async (_event: unknown, cb: unknown) => {
    handler = cb as (e: { payload: PluginDonePayload }) => void;
    return () => {};
  });
  return () => handler;
}

describe("Plugins page - listele/kur/kaldir/guncelle/denetle dallari", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("renders installed plugin rows with update and remove buttons", async () => {
    mockRpc({ "plugin.list": INSTALLED });
    renderPlugins();
    await screen.findByText("plasmoid-x");
    expect(screen.getByText("120 B")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Güncelle plasmoid-x" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaldır plasmoid-x" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Kurulu \(1\)/ })).toBeInTheDocument();
  });

  it("shows error toast when plugin.list fails", async () => {
    mockRpc({}, { "plugin.list": { code: -32000, message: "liste bozuk" } });
    renderPlugins();
    expect(await screen.findByText(/liste bozuk/)).toBeInTheDocument();
  });

  it("shows skeletons while installed plugins load", () => {
    invokeMock.mockImplementation(() => new Promise(() => {}));
    const { container } = renderPlugins();
    expect(container.querySelectorAll(".animate-pulse").length).toBe(2);
  });

  it("loads and lists available plugins when switching tab", async () => {
    mockRpc({ "plugin.list": INSTALLED, "plugin.available": AVAILABLE });
    renderPlugins();
    await screen.findByText("plasmoid-x");
    fireEvent.click(screen.getByRole("button", { name: "Kullanılabilir" }));
    await screen.findByText("pkg-browser");
    expect(screen.getByText("v1.2.0")).toBeInTheDocument();
    expect(screen.getByText("Paket gezgini")).toBeInTheDocument();
    expect(callsFor("plugin.available").length).toBe(1);
  });

  it("shows skeletons while available plugins load", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
      if (payload.method === "plugin.available") return new Promise(() => {});
      return Promise.resolve({ jsonrpc: "2.0", id: 1, result: [], error: null });
    });
    const { container } = renderPlugins();
    await screen.findByText(/Yerel plugin yok/i);
    fireEvent.click(screen.getByRole("button", { name: "Kullanılabilir" }));
    await vi.waitFor(() =>
      expect(container.querySelectorAll(".animate-pulse").length).toBe(2),
    );
  });

  it("shows empty state with refresh button on available tab", async () => {
    mockRpc({});
    renderPlugins();
    await screen.findByText(/Yerel plugin yok/i);
    fireEvent.click(screen.getByRole("button", { name: "Kullanılabilir" }));
    expect(await screen.findByText(/Plugin bulunamadı/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yenile" })).toBeInTheDocument();
  });

  it("refresh button re-fetches available plugins", async () => {
    mockRpc({});
    renderPlugins();
    await screen.findByText(/Yerel plugin yok/i);
    fireEvent.click(screen.getByRole("button", { name: "Kullanılabilir" }));
    await screen.findByText(/Plugin bulunamadı/);
    fireEvent.click(screen.getByRole("button", { name: "Yenile" }));
    await vi.waitFor(() => expect(callsFor("plugin.available").length).toBe(2));
  });

  it("shows error toast when plugin.available fails", async () => {
    mockRpc({}, { "plugin.available": { code: -32001, message: "pazar erisilemez" } });
    renderPlugins();
    await screen.findByText(/Yerel plugin yok/i);
    fireEvent.click(screen.getByRole("button", { name: "Kullanılabilir" }));
    expect(await screen.findByText(/pazar erisilemez/)).toBeInTheDocument();
  });

  it("switches back to installed tab", async () => {
    mockRpc({ "plugin.list": INSTALLED, "plugin.available": AVAILABLE });
    renderPlugins();
    await screen.findByText("plasmoid-x");
    fireEvent.click(screen.getByRole("button", { name: "Kullanılabilir" }));
    await screen.findByText("pkg-browser");
    fireEvent.click(screen.getByRole("button", { name: /Kurulu/ }));
    await screen.findByText("plasmoid-x");
    expect(screen.queryByText("pkg-browser")).not.toBeInTheDocument();
  });

  it("does not refetch available plugins once loaded", async () => {
    mockRpc({ "plugin.list": INSTALLED, "plugin.available": AVAILABLE });
    renderPlugins();
    await screen.findByText("plasmoid-x");
    fireEvent.click(screen.getByRole("button", { name: "Kullanılabilir" }));
    await screen.findByText("pkg-browser");
    fireEvent.click(screen.getByRole("button", { name: /Kurulu/ }));
    await screen.findByText("plasmoid-x");
    fireEvent.click(screen.getByRole("button", { name: "Kullanılabilir" }));
    await screen.findByText("pkg-browser");
    expect(callsFor("plugin.available").length).toBe(1);
  });

  it("install button calls plugin.install and disables while busy", async () => {
    mockRpc({ "plugin.available": AVAILABLE });
    renderPlugins();
    await screen.findByText(/Yerel plugin yok/i);
    fireEvent.click(screen.getByRole("button", { name: "Kullanılabilir" }));
    const installBtn = await screen.findByRole("button", { name: "Kur" });
    fireEvent.click(installBtn);
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "plugin.install",
          params: { name: "pkg-browser" },
        }),
      ),
    );
    expect(installBtn).toBeDisabled();
  });

  it("shows error toast when plugin.install fails and re-enables button", async () => {
    mockRpc(
      { "plugin.available": AVAILABLE },
      { "plugin.install": { code: -32002, message: "kurulum hatasi" } },
    );
    renderPlugins();
    await screen.findByText(/Yerel plugin yok/i);
    fireEvent.click(screen.getByRole("button", { name: "Kullanılabilir" }));
    const installBtn = await screen.findByRole("button", { name: "Kur" });
    fireEvent.click(installBtn);
    expect(await screen.findByText(/kurulum hatasi/)).toBeInTheDocument();
    await vi.waitFor(() => expect(installBtn).toBeEnabled());
  });

  it("update button calls plugin.update", async () => {
    mockRpc({ "plugin.list": INSTALLED });
    renderPlugins();
    fireEvent.click(await screen.findByRole("button", { name: "Güncelle plasmoid-x" }));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "plugin.update",
          params: { name: "plasmoid-x" },
        }),
      ),
    );
  });

  it("shows error toast when plugin.update fails", async () => {
    mockRpc(
      { "plugin.list": INSTALLED },
      { "plugin.update": { code: -32003, message: "guncelleme hatasi" } },
    );
    renderPlugins();
    fireEvent.click(await screen.findByRole("button", { name: "Güncelle plasmoid-x" }));
    expect(await screen.findByText(/guncelleme hatasi/)).toBeInTheDocument();
  });

  it("remove button calls plugin.uninstall, toasts success and reloads list", async () => {
    mockRpc({ "plugin.list": INSTALLED });
    renderPlugins();
    fireEvent.click(await screen.findByRole("button", { name: "Kaldır plasmoid-x" }));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "plugin.uninstall",
          params: { name: "plasmoid-x" },
        }),
      ),
    );
    expect(await screen.findByText(/plasmoid-x kaldırıldı/)).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(callsFor("plugin.list").length).toBeGreaterThanOrEqual(2),
    );
  });

  it("shows error toast when plugin.uninstall fails and skips reload", async () => {
    mockRpc(
      { "plugin.list": INSTALLED },
      { "plugin.uninstall": { code: -32004, message: "kaldirma hatasi" } },
    );
    renderPlugins();
    fireEvent.click(await screen.findByRole("button", { name: "Kaldır plasmoid-x" }));
    expect(await screen.findByText(/kaldirma hatasi/)).toBeInTheDocument();
    expect(callsFor("plugin.list").length).toBe(1);
  });

  it("audit button loads and renders results with status badges", async () => {
    mockRpc({ "plugin.list": INSTALLED, "plugin.audit": AUDITS });
    renderPlugins();
    await screen.findByText("plasmoid-x");
    fireEvent.click(screen.getByRole("button", { name: "Denetle" }));
    expect(await screen.findByText("Denetim Sonuçları")).toBeInTheDocument();
    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.getByText("bozuk")).toBeInTheDocument();
    expect(screen.getByText("saglam")).toBeInTheDocument();
    expect(screen.getByText("imza hatasi")).toBeInTheDocument();
    expect(screen.getByText("eski-eklenti")).toBeInTheDocument();
  });

  it("shows error toast when plugin.audit fails", async () => {
    mockRpc(
      { "plugin.list": INSTALLED },
      { "plugin.audit": { code: -32005, message: "denetim hatasi" } },
    );
    renderPlugins();
    await screen.findByText("plasmoid-x");
    fireEvent.click(screen.getByRole("button", { name: "Denetle" }));
    expect(await screen.findByText(/denetim hatasi/)).toBeInTheDocument();
  });
});

describe("Plugins page - event/plugin_done dallari", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  async function firePluginDone(payload: PluginDonePayload) {
    const getHandler = capturePluginDoneHandler();
    renderPlugins();
    await screen.findByText(/Yerel plugin yok/i);
    const handler = await vi.waitFor(() => {
      const h = getHandler();
      expect(h).toBeDefined();
      return h as (e: { payload: PluginDonePayload }) => void;
    });
    await act(async () => {
      handler({ payload });
    });
  }

  it("success event shows result message toast and reloads installed", async () => {
    mockRpc({ "plugin.list": [] });
    await firePluginDone({ ok: true, result: { message: "Eklenti kuruldu" } });
    expect(await screen.findByText("Eklenti kuruldu")).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(callsFor("plugin.list").length).toBeGreaterThanOrEqual(2),
    );
  });

  it("success event without message falls back to plugDone toast", async () => {
    mockRpc({});
    await firePluginDone({ ok: true });
    expect(await screen.findByText("İşlem tamamlandı")).toBeInTheDocument();
  });

  it("failure event shows error toast", async () => {
    mockRpc({});
    await firePluginDone({ ok: false, error: "indirme basarisiz" });
    expect(await screen.findByText(/indirme basarisiz/)).toBeInTheDocument();
  });

  it("failure event without error falls back to plugFail toast", async () => {
    mockRpc({});
    await firePluginDone({ ok: false });
    expect(await screen.findByText("Plugin işlemi başarısız")).toBeInTheDocument();
  });
});
