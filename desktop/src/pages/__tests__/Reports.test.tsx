import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Reports } from "../Reports";
import { ToastProvider } from "../../components/ui/Toast";
import { cacheInvalidate } from "../../lib/cache";
import { listen } from "@tauri-apps/api/event";

function renderReports() {
  return render(
    <ToastProvider>
      <Reports />
    </ToastProvider>,
  );
}

const HEALTH = {
  total: 10, installed: 6, converted: 2, failed: 2, success_rate: 80,
  by_type: { deb: 7, rpm: 3 }, by_arch: { x86_64: 10 }, url_count: 4,
  first_seen: "2026-08-01", last_seen: "2026-08-22",
};

const HEALTH_EMPTY = {
  total: 0, installed: 0, converted: 0, failed: 0, success_rate: 0,
  by_type: {}, by_arch: {}, url_count: 0,
  first_seen: "", last_seen: "",
};

// --- RPC response helpers ---

function rpcOk(result: unknown) {
  return { jsonrpc: "2.0", id: 1, result, error: null };
}

function rpcErr(code: number, message: string) {
  return { jsonrpc: "2.0", id: 1, result: null, error: { code, message } };
}

/** Her RPC metodunu kendi yanitina yonlendirir; listelenmeyenler null result alir. */
function mockRpc(responses: Record<string, unknown>) {
  invokeMock.mockImplementation(async (_cmd: unknown, args: { method?: string } = {}) => {
    const method = args?.method ?? "";
    return method in responses ? responses[method] : rpcOk(null);
  });
}

function methodCalls(method: string): number {
  return invokeMock.mock.calls.filter(
    (c: unknown[]) => (c[1] as { method?: string } | undefined)?.method === method,
  ).length;
}

// --- Push-event helper'lari: listen mock'i handler'lari kaydeder, biz tetikleriz ---

const listenMock = listen as unknown as ReturnType<typeof vi.fn>;

function listening(event: string): boolean {
  return listenMock.mock.calls.some((c: unknown[]) => c[0] === event);
}

function emit(event: string, payload: unknown) {
  const hit = listenMock.mock.calls.find((c: unknown[]) => c[0] === event);
  if (!hit) throw new Error(`no listener registered for ${event}`);
  act(() => {
    (hit[1] as (e: { payload: unknown }) => void)({ payload });
  });
}

// --- jsdom stub'lari: clipboard, object URL'leri ve anchor indirmeleri ---

const clipboardWriteText = vi.fn();
// userEvent.setup() kendine ait bir navigator.clipboard stub'i kurar; bizim
// mock'un gorunur kalmasi icin her test oncesinde yeniden yerlestirilir.
function installClipboardStub() {
  try {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: clipboardWriteText },
      configurable: true,
      writable: true,
    });
  } catch {
    (navigator as unknown as Record<string, unknown>).clipboard = {
      writeText: clipboardWriteText,
    };
  }
}
installClipboardStub();

const createObjectURLMock = vi.fn((_blob: Blob) => "blob:mock-url");
const revokeObjectURLMock = vi.fn();
Object.defineProperty(URL, "createObjectURL", {
  value: createObjectURLMock,
  configurable: true,
  writable: true,
});
Object.defineProperty(URL, "revokeObjectURL", {
  value: revokeObjectURLMock,
  configurable: true,
  writable: true,
});
const anchorClickSpy = vi
  .spyOn(HTMLAnchorElement.prototype, "click")
  .mockImplementation(() => {});

/** Saglikli istatistiklerle render et ve dashboard'un yerlesmesini bekle. */
async function renderHealthy(extra: Record<string, unknown> = {}) {
  mockRpc({
    "system.health": rpcOk(HEALTH),
    "system.snapshot_status": rpcOk({ installed: false }),
    ...extra,
  });
  const view = renderReports();
  await screen.findByText("80%");
  return view;
}

describe("Reports page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    // Faz 8 health cache'i modul kapsamli; her test soguk baslasin diye dusur.
    cacheInvalidate("reports.health");
    listenMock.mockClear();
    clipboardWriteText.mockReset();
    clipboardWriteText.mockResolvedValue(undefined);
    installClipboardStub();
    createObjectURLMock.mockClear();
    revokeObjectURLMock.mockClear();
    anchorClickSpy.mockClear();
  });

  it("loads health stats on mount", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: HEALTH });
    renderReports();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "system.health" }),
      ),
    );
  });

  it("shows success rate", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: HEALTH });
    renderReports();
    await vi.waitFor(() => expect(screen.getByText(/80/)).toBeInTheDocument());
  });

  it("has a benchmark run button", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: HEALTH });
    renderReports();
    await vi.waitFor(() => expect(screen.getByText("Benchmark Çalıştır")).toBeInTheDocument());
  });

  it("has a rollback verify button", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: HEALTH });
    renderReports();
    await vi.waitFor(() => expect(screen.getByText("Rollback Doğrula")).toBeInTheDocument());
  });

  // --- Faz 10: Markdown export / copy ---

  it("exports the health report as a Markdown file (Faz 10)", async () => {
    const user = userEvent.setup();
    await renderHealthy();
    await user.click(screen.getByRole("button", { name: "Markdown indir" }));
    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    const blob = createObjectURLMock.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("text/markdown;charset=utf-8");
    const text = await blob.text();
    expect(text).toContain("# PkgForge System Report");
    expect(text).toContain("- total: 10");
    expect(text).toContain("- success_rate: 80%");
    expect(text).toContain("- deb: 7");
    expect(text).toContain("- rpm: 3");
    expect(anchorClickSpy).toHaveBeenCalledTimes(1);
    const anchor = anchorClickSpy.mock.instances[0] as HTMLAnchorElement;
    expect(anchor.download).toBe("pkgforge-report.md");
    expect(revokeObjectURLMock).toHaveBeenCalledWith("blob:mock-url");
  });

  it("copies the Markdown report to the clipboard (Faz 10)", async () => {
    await renderHealthy();
    // fireEvent: userEvent.setup() navigator.clipboard stub'imizi degistirirdi.
    fireEvent.click(screen.getByRole("button", { name: "Kopyala" }));
    await vi.waitFor(() => expect(clipboardWriteText).toHaveBeenCalledTimes(1));
    const md = clipboardWriteText.mock.calls[0][0] as string;
    expect(md).toContain("# PkgForge System Report");
    expect(md).toContain("- installed: 6");
    expect(await screen.findByText("Rapor kopyalandı")).toBeInTheDocument();
  });

  it("toasts an error when copying the report fails (Faz 10)", async () => {
    clipboardWriteText.mockRejectedValue(new Error("clipboard blocked"));
    await renderHealthy();
    // fireEvent: userEvent.setup() navigator.clipboard stub'imizi degistirirdi.
    fireEvent.click(screen.getByRole("button", { name: "Kopyala" }));
    expect(await screen.findByText("Rapor kopyalanamadı")).toBeInTheDocument();
  });

  it("exports the raw health stats as JSON (Faz 9)", async () => {
    const user = userEvent.setup();
    await renderHealthy();
    await user.click(screen.getByRole("button", { name: "JSON İndir" }));
    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    const blob = createObjectURLMock.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("application/json");
    expect(JSON.parse(await blob.text())).toMatchObject({ total: 10, success_rate: 80 });
    const anchor = anchorClickSpy.mock.instances[0] as HTMLAnchorElement;
    expect(anchor.download).toBe("pkgforge-report.json");
  });

  // --- Health yukleme: bos durum / hata / cache dallari ---

  it("shows the empty state when no conversions exist yet", async () => {
    mockRpc({
      "system.health": rpcOk(HEALTH_EMPTY),
      "system.snapshot_status": rpcOk({ installed: false }),
    });
    renderReports();
    expect(await screen.findByText("Henüz kayıtlı dönüşüm yok")).toBeInTheDocument();
    expect(screen.getByText(/İlk dönüşümünüzü yaptığınızda/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Markdown indir" })).toBeEnabled();
  });

  it("shows the error state and disables exports when health load fails", async () => {
    mockRpc({
      "system.health": rpcErr(-32000, "sidecar bağlı değil"),
      "system.snapshot_status": rpcErr(-32000, "sidecar bağlı değil"),
    });
    renderReports();
    expect(await screen.findByText("Bir şeyler ters gitti")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Markdown indir" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Kopyala" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "JSON İndir" })).toBeDisabled();
    expect(screen.getAllByText(/sidecar bağlı değil/).length).toBeGreaterThan(0);
  });

  it("recovers through the retry button after a failed load", async () => {
    mockRpc({ "system.health": rpcErr(-32000, "geçici hata") });
    renderReports();
    await screen.findByText("Bir şeyler ters gitti");
    mockRpc({
      "system.health": rpcOk(HEALTH),
      "system.snapshot_status": rpcOk({ installed: false }),
    });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    expect(await screen.findByText("80%")).toBeInTheDocument();
  });

  it("shows a skeleton and disables exports while health is still loading", () => {
    invokeMock.mockImplementation(() => new Promise(() => {}));
    const { container } = renderReports();
    expect(screen.getByRole("button", { name: "Markdown indir" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Kopyala" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "JSON İndir" })).toBeDisabled();
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("force-refreshes health through the Yenile button, bypassing the cache", async () => {
    await renderHealthy();
    expect(methodCalls("system.health")).toBe(1);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Yenile" }));
    await vi.waitFor(() => expect(methodCalls("system.health")).toBe(2));
  });

  it("serves health from the cache on remount within the TTL", async () => {
    const first = await renderHealthy();
    first.unmount();
    renderReports();
    await screen.findByText("80%");
    expect(methodCalls("system.health")).toBe(1);
  });

  it("renders the type distribution with percentages", async () => {
    await renderHealthy();
    expect(screen.getByText("deb")).toBeInTheDocument();
    expect(screen.getByText("7 (70%)")).toBeInTheDocument();
    expect(screen.getByText("rpm")).toBeInTheDocument();
    expect(screen.getByText("3 (30%)")).toBeInTheDocument();
  });

  // --- Benchmark dallari ---

  it("runs the benchmark and renders results from the bench_done event", async () => {
    await renderHealthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Benchmark Çalıştır" }));
    await vi.waitFor(() => expect(listening("event/bench_done")).toBe(true));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "system.benchmark", params: { quick: true } }),
      ),
    );
    expect(screen.getByRole("button", { name: "Benchmark Çalıştır" })).toBeDisabled();
    emit("event/bench_done", {
      ok: true,
      result: {
        results: [
          { name: "cold-scan", duration_ms: 120, memory_peak_kb: 4200, input_size_bytes: 1, output_size_bytes: 1, details: "", passed: true },
          { name: "warm-scan", duration_ms: 8, memory_peak_kb: 900, input_size_bytes: 1, output_size_bytes: 1, details: "", passed: false },
        ],
        total_duration_ms: 128,
        passed: false,
      },
    });
    expect(await screen.findByText("cold-scan")).toBeInTheDocument();
    expect(screen.getByText("120ms")).toBeInTheDocument();
    expect(screen.getByText("4200KB")).toBeInTheDocument();
    expect(screen.getByText("geçti")).toBeInTheDocument();
    expect(screen.getByText("kaldı")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Benchmark Çalıştır" })).toBeEnabled();
  });

  it("toasts the error when the benchmark RPC fails", async () => {
    await renderHealthy({ "system.benchmark": rpcErr(-1, "benchmark patladı") });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Benchmark Çalıştır" }));
    expect(await screen.findByText(/benchmark patladı/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Benchmark Çalıştır" })).toBeEnabled();
  });

  it("surfaces the bench_done error payload as a toast", async () => {
    await renderHealthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Benchmark Çalıştır" }));
    await vi.waitFor(() => expect(listening("event/bench_done")).toBe(true));
    emit("event/bench_done", { ok: false, error: "disk dolu" });
    expect(await screen.findByText("disk dolu")).toBeInTheDocument();
  });

  it("falls back to the generic benchmark failure toast", async () => {
    await renderHealthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Benchmark Çalıştır" }));
    await vi.waitFor(() => expect(listening("event/bench_done")).toBe(true));
    emit("event/bench_done", { ok: false });
    expect(await screen.findByText("Benchmark başarısız")).toBeInTheDocument();
  });

  // --- Rollback dogrulama dallari ---

  it("verifies the rollback and shows the verified result", async () => {
    await renderHealthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Rollback Doğrula" }));
    await vi.waitFor(() => expect(listening("event/system_done")).toBe(true));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "system.verify_rollback" }),
      ),
    );
    expect(screen.getByRole("button", { name: "Rollback Doğrula" })).toBeDisabled();
    emit("event/system_done", {
      ok: true,
      result: {
        verified: true, backend: "btrfs", snapshot_name: "snap-2026-08",
        detail: "dosyalar temiz", files_checked: 12, state_before: "ok", state_after: "ok",
      },
    });
    expect(await screen.findByText("Doğrulandı")).toBeInTheDocument();
    expect(screen.getByText("backend: btrfs")).toBeInTheDocument();
    expect(screen.getByText("dosyalar temiz")).toBeInTheDocument();
    expect(screen.getByText("snap-2026-08")).toBeInTheDocument();
  });

  it("shows the no-backend state when rollback verification finds none", async () => {
    await renderHealthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Rollback Doğrula" }));
    await vi.waitFor(() => expect(listening("event/system_done")).toBe(true));
    emit("event/system_done", {
      ok: true,
      result: {
        verified: false, backend: "none", snapshot_name: "",
        detail: "", files_checked: 0, state_before: "", state_after: "",
      },
    });
    expect(await screen.findByText("Snapshot altyapısı yok")).toBeInTheDocument();
    expect(screen.getByText(/Btrfs veya ZFS/)).toBeInTheDocument();
  });

  it("shows the not-verified badge when verification fails", async () => {
    await renderHealthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Rollback Doğrula" }));
    await vi.waitFor(() => expect(listening("event/system_done")).toBe(true));
    emit("event/system_done", {
      ok: true,
      result: {
        verified: false, backend: "zfs", snapshot_name: "",
        detail: "bozuk dosya", files_checked: 3, state_before: "ok", state_after: "bad",
      },
    });
    expect(await screen.findByText("Doğrulanamadı")).toBeInTheDocument();
    expect(screen.getByText("bozuk dosya")).toBeInTheDocument();
  });

  it("toasts the error when the verify_rollback RPC fails", async () => {
    await renderHealthy({ "system.verify_rollback": rpcErr(-2, "rollback okunamadı") });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Rollback Doğrula" }));
    expect(await screen.findByText(/rollback okunamadı/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rollback Doğrula" })).toBeEnabled();
  });

  it("falls back to the generic rollback failure toast", async () => {
    await renderHealthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Rollback Doğrula" }));
    await vi.waitFor(() => expect(listening("event/system_done")).toBe(true));
    emit("event/system_done", { ok: false });
    expect(await screen.findByText("Rollback doğrulama başarısız")).toBeInTheDocument();
  });

  // --- Snapshot durumu / kurma / kaldirma dallari ---

  it("shows the installed badge from snapshot_status", async () => {
    await renderHealthy({ "system.snapshot_status": rpcOk({ installed: true }) });
    // "Kurulu" ayni zamanda health grid'indeki installed etiketi; snapshot kartina kapsamla.
    const snapCard = screen.getByText("Snapshot Temizlik Servisi").closest("div")?.parentElement;
    expect(await within(snapCard as HTMLElement).findByText("Kurulu")).toBeInTheDocument();
  });

  it("shows the not-installed badge from snapshot_status", async () => {
    await renderHealthy({ "system.snapshot_status": rpcOk({ installed: false }) });
    expect(await screen.findByText("Kurulu değil")).toBeInTheDocument();
  });

  it("falls back to the active flag in snapshot_status", async () => {
    await renderHealthy({ "system.snapshot_status": rpcOk({ active: true }) });
    // "Kurulu" ayni zamanda health grid'indeki installed etiketi; snapshot kartina kapsamla.
    const snapCard = screen.getByText("Snapshot Temizlik Servisi").closest("div")?.parentElement;
    expect(await within(snapCard as HTMLElement).findByText("Kurulu")).toBeInTheDocument();
  });

  it("installs the snapshot and reports success via snapshot_done", async () => {
    let resolveInstall: ((v: unknown) => void) | undefined;
    const pendingInstall = new Promise((res) => {
      resolveInstall = res;
    });
    invokeMock.mockImplementation(async (_cmd: unknown, args: { method?: string } = {}) => {
      if (args?.method === "system.snapshot_install") return pendingInstall;
      if (args?.method === "system.snapshot_status") return rpcOk({ installed: false });
      if (args?.method === "system.health") return rpcOk(HEALTH);
      return rpcOk(null);
    });
    renderReports();
    await screen.findByText("80%");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Kur" }));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "system.snapshot_install", params: { max_age_days: 7 } }),
      ),
    );
    // pkexec diyaloğu beklerken her iki snapshot butonu da devre disi.
    expect(screen.getByRole("button", { name: "Kur" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Kaldır" })).toBeDisabled();
    resolveInstall?.(rpcOk({ started: true }));
    emit("event/snapshot_done", { ok: true, result: { ok: true, message: "Snapshot kuruldu" } });
    expect(await screen.findByText("Snapshot kuruldu")).toBeInTheDocument();
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Kur" })).toBeEnabled());
    // Event sonrasi durum yeniden sorgulanir.
    expect(methodCalls("system.snapshot_status")).toBeGreaterThanOrEqual(2);
  });

  it("removes the snapshot and surfaces a snapshot_done failure", async () => {
    await renderHealthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Kaldır" }));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "system.snapshot_remove" }),
      ),
    );
    emit("event/snapshot_done", { ok: false, error: "yetki reddedildi" });
    expect(await screen.findByText("yetki reddedildi")).toBeInTheDocument();
  });

  it("toasts the error and re-enables buttons when snapshot install fails", async () => {
    await renderHealthy({ "system.snapshot_install": rpcErr(-3, "pkexec çalışmadı") });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Kur" }));
    expect(await screen.findByText(/pkexec çalışmadı/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kur" })).toBeEnabled();
  });

  it("uses the generic snapshot failure toast when the event has no error", async () => {
    await renderHealthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Kaldır" }));
    await vi.waitFor(() => expect(listening("event/snapshot_done")).toBe(true));
    emit("event/snapshot_done", { ok: false });
    expect(await screen.findByText("Snapshot işlemi başarısız")).toBeInTheDocument();
  });

  // --- Yillik ozet dialogu ---

  it("opens the annual wrapped dialog and requests stats.wrapped", async () => {
    await renderHealthy({
      "stats.wrapped": rpcOk({
        year: 2026, total: 0, success: 0, failed: 0, success_rate: 0,
        by_type: {}, by_month: {}, top_packages: [], distinct_packages: 0,
        busiest_month: "", url_count: 0,
      }),
    });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Yıl Özeti" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "stats.wrapped" }),
      ),
    );
  });
});