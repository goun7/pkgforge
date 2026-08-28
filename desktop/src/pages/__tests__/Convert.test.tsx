import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// --- Mock the Tauri API surface used by Convert / rpc ---
const listeners = new Map<string, (e: { payload: unknown }) => void>();

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn((event: string, cb: (e: { payload: unknown }) => void) => {
    listeners.set(event, cb);
    return Promise.resolve(() => listeners.delete(event));
  }),
}));

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

// DropZone's dynamic import of the dialog plugin must resolve to a stub.
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn().mockResolvedValue([]),
}));

import { open } from "@tauri-apps/plugin-dialog";
import { Convert } from "../Convert";
import { ToastProvider } from "../../components/ui/Toast";

function renderConvert() {
  return render(
    <ToastProvider>
      <Convert />
    </ToastProvider>,
  );
}

function emit(event: string, payload: unknown) {
  const cb = listeners.get(event);
  if (cb) cb({ payload });
}

// --- Ortak yardimcilar / fiksturler ---
type RpcReq = { id: number; method: string; params?: unknown };

function rpcOk(result: unknown) {
  return { jsonrpc: "2.0", id: 1, result, error: null };
}

function rpcErr(code: number, message: string) {
  return { jsonrpc: "2.0", id: 1, result: null, error: { code, message } };
}

function callsTo(method: string) {
  return invokeMock.mock.calls.filter(
    (c) => (c[1] as RpcReq | undefined)?.method === method,
  );
}

/** invokeMock'u method adina gore yanitlandirir; eslesmeyenler { ok: true } alir. */
function mockRpc(handlers: Record<string, unknown>) {
  invokeMock.mockImplementation((_cmd: string, req: RpcReq) =>
    Promise.resolve(
      handlers[req.method] ?? { jsonrpc: "2.0", id: req.id, result: { ok: true }, error: null },
    ),
  );
}

/** Bir dosya birak, pipeline.start cagrisini ve calisan durumu bekle. */
async function startRunning(path = "/tmp/akan.deb") {
  act(() => emit("tauri://drag-drop", { paths: [path] }));
  await vi.waitFor(() => expect(callsTo("pipeline.start")).toHaveLength(1));
  await vi.waitFor(() => expect(screen.getByText("çalışıyor…")).toBeInTheDocument());
}

/** Calisan donusumu basariyla bitir ve sonuc bandini bekle. */
async function finishSuccess(pkg = "/out/sonuc.pkg.tar.zst") {
  act(() =>
    emit("event/finished", { success: true, message: "donusum bitti", output_pkg: pkg }),
  );
  await vi.waitFor(() =>
    expect(screen.getByText("Dönüşüm tamamlandı")).toBeInTheDocument(),
  );
}

/** Panoyu taklit eder; test sonunda kaldirilir. */
function mockClipboard(writeText: (text: string) => Promise<void>) {
  const spy = vi.fn(writeText);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText: spy },
    configurable: true,
  });
  return spy;
}
function clearClipboard() {
  delete (navigator as { clipboard?: unknown }).clipboard;
}

const GRAPH_DATA = {
  root: "ana",
  nodes: {
    ana: { name: "ana", version: "1.0", deps: ["bag"], needed_by: [], is_installed: true, is_foreign: false },
    bag: { name: "bag", version: "2.0", deps: [], needed_by: ["ana"], is_installed: false, is_foreign: false },
  },
  stats: { total: 2, installed: 1, missing: 1, foreign: 0, max_depth: 1 },
  mermaid: "",
  warnings: [],
};

const BATCH_ITEMS = [
  { id: "/tmp/a.deb", path: "/tmp/a.deb", name: "a.deb", status: "running", priority: 0, message: "" },
  { id: "/tmp/b.deb", path: "/tmp/b.deb", name: "b.deb", status: "pending", priority: 1, message: "sira bekliyor" },
  { id: "/tmp/c.deb", path: "/tmp/c.deb", name: "c.deb", status: "done", priority: 2, message: "" },
  { id: "/tmp/d.deb", path: "/tmp/d.deb", name: "d.deb", status: "error", priority: 3, message: "donusturulemedi" },
];

/** Toplu sekmesine gec ve kuyruk ogelerinin listelenmesini bekle. */
async function openBatchTab() {
  mockRpc({ "queue.list": rpcOk(BATCH_ITEMS) });
  fireEvent.click(screen.getByText("Toplu"));
  await vi.waitFor(() => expect(screen.getByText("a.deb")).toBeInTheDocument());
}

describe("Convert page", () => {
  beforeEach(() => {
    listeners.clear();
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ started: true });
  });

  it("renders the drop zone and empty queue", () => {
    renderConvert();
    expect(screen.getByRole("button", { name: "Paket bırakma alanı" })).toBeInTheDocument();
    expect(screen.getByText("Kuyruk (0)")).toBeInTheDocument();
  });

  it("subscribes to pipeline events on mount", () => {
    renderConvert();
    expect(listeners.has("event/step_changed")).toBe(true);
    expect(listeners.has("event/progress")).toBe(true);
    expect(listeners.has("event/log")).toBe(true);
    expect(listeners.has("event/finished")).toBe(true);
  });

  it("starts the pipeline when a path is dropped", async () => {
    renderConvert();
    // Simulate a native drag-drop with a real path.
    emit("tauri://drag-drop", { paths: ["/tmp/pkg_1.0_amd64.deb"] });
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "pipeline.start" }),
      ),
    );
    expect(screen.getByText("pkg_1.0_amd64.deb")).toBeInTheDocument();
  });

  it("marks the running item failed when finished reports failure", async () => {
    renderConvert();
    emit("tauri://drag-drop", { paths: ["/tmp/bad.deb"] });
    await vi.waitFor(() => expect(invokeMock).toHaveBeenCalled());
    emit("event/finished", { success: false, message: "analiz hatası" });
    await vi.waitFor(() => expect(screen.getByText("Başarısız")).toBeInTheDocument());
  });

  it("shows the compatibility dialog and approves install", async () => {
    renderConvert();
    emit("tauri://drag-drop", { paths: ["/tmp/warn.deb"] });
    await vi.waitFor(() => expect(invokeMock).toHaveBeenCalled());
    emit("event/compatibility_ready", {
      report: {
        overall: "warning",
        grade: "B",
        checks: [{ name: "deps", severity: "warning", message: "eksik bağımlılık", details: [] }],
      },
    });
    await vi.waitFor(() =>
      expect(screen.getByText(/Uyumluluk Raporu/)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText("Yine de Kur"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "pipeline.approve" }),
      ),
    );
  });

  it("renders the batch tab and loads the queue on switch", async () => {
    invokeMock.mockResolvedValue([]);
    renderConvert();
    fireEvent.click(screen.getByText("Toplu"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "queue.list" }),
      ),
    );
    expect(screen.getByText("Toplu Dönüştürme")).toBeInTheDocument();
  });

  // --- Faz 9 (5.6): tam ekran drop overlay ---
  it("shows the drop overlay on drag-enter and hides it on drag-leave", async () => {
    renderConvert();
    expect(screen.queryByText("Paketleri buraya bırakın")).not.toBeInTheDocument();
    act(() => emit("tauri://drag-enter", {}));
    await vi.waitFor(() =>
      expect(screen.getByText("Paketleri buraya bırakın")).toBeInTheDocument(),
    );
    act(() => emit("tauri://drag-leave", {}));
    await vi.waitFor(() =>
      expect(screen.queryByText("Paketleri buraya bırakın")).not.toBeInTheDocument(),
    );
  });

  // --- Dosya sec (browse dialog) ---
  it("adds files picked from the browse dialog and starts the pipeline", async () => {
    vi.mocked(open).mockResolvedValueOnce(["/tmp/secim.deb"]);
    renderConvert();
    fireEvent.click(screen.getByRole("button", { name: "Paket bırakma alanı" }));
    await vi.waitFor(() => expect(callsTo("pipeline.start")).toHaveLength(1));
    expect(callsTo("pipeline.start")[0][1]).toEqual(
      expect.objectContaining({ params: { path: "/tmp/secim.deb" } }),
    );
    await vi.waitFor(() => expect(screen.getByText("secim.deb")).toBeInTheDocument());
  });

  it("keeps the queue empty when the browse dialog is dismissed", async () => {
    vi.mocked(open).mockResolvedValueOnce(null as unknown as string[]);
    renderConvert();
    fireEvent.click(screen.getByRole("button", { name: "Paket bırakma alanı" }));
    await vi.waitFor(() => expect(vi.mocked(open)).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 20));
    expect(callsTo("pipeline.start")).toHaveLength(0);
    expect(screen.getByText("Kuyruk (0)")).toBeInTheDocument();
  });

  it("does not queue a path that is already queued", async () => {
    renderConvert();
    act(() => emit("tauri://drag-drop", { paths: ["/tmp/ayni.deb"] }));
    await vi.waitFor(() => expect(callsTo("pipeline.start")).toHaveLength(1));
    act(() => emit("tauri://drag-drop", { paths: ["/tmp/ayni.deb"] }));
    await new Promise((r) => setTimeout(r, 20));
    expect(callsTo("pipeline.start")).toHaveLength(1);
    expect(screen.getByText("Kuyruk (1)")).toBeInTheDocument();
  });

  it("removes a pending item from the queue", async () => {
    renderConvert();
    act(() => emit("tauri://drag-drop", { paths: ["/tmp/ilk.deb", "/tmp/ikinci.deb"] }));
    await vi.waitFor(() => expect(callsTo("pipeline.start")).toHaveLength(1));
    await vi.waitFor(() => expect(screen.getByText("Kuyruk (2)")).toBeInTheDocument());
    // Calisan ogu icin kaldir butonu yok, bekleyen icin var.
    expect(screen.queryByRole("button", { name: "Kaldır ilk.deb" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Kaldır ikinci.deb" }));
    await vi.waitFor(() => expect(screen.getByText("Kuyruk (1)")).toBeInTheDocument());
    expect(screen.queryByText("ikinci.deb")).not.toBeInTheDocument();
  });

  it("marks the queue item failed when pipeline.start returns an RPC error", async () => {
    invokeMock.mockResolvedValue(rpcErr(-1, "sidecar hazir degil"));
    renderConvert();
    act(() => emit("tauri://drag-drop", { paths: ["/tmp/hata.deb"] }));
    await vi.waitFor(() => expect(screen.getByText("Başarısız")).toBeInTheDocument());
    expect(screen.getByText(/sidecar hazir degil/)).toBeInTheDocument();
  });

  // --- Iptal onay akisi (Faz 8 2.6) ---
  it("opens the cancel confirm dialog and backs out without cancelling", async () => {
    renderConvert();
    await startRunning();
    fireEvent.click(screen.getByRole("button", { name: "İptal" }));
    expect(await screen.findByText("Dönüşümü iptal et")).toBeInTheDocument();
    expect(
      screen.getByText("Çalışan dönüşüm iptal edilecek. Devam edilsin mi?"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText("Vazgeç"));
    await vi.waitFor(() =>
      expect(screen.queryByText("Dönüşümü iptal et")).not.toBeInTheDocument(),
    );
    expect(callsTo("pipeline.cancel")).toHaveLength(0);
  });

  it("confirming the cancel dialog calls pipeline.cancel", async () => {
    renderConvert();
    await startRunning();
    fireEvent.click(screen.getByRole("button", { name: "İptal" }));
    fireEvent.click(await screen.findByText("Onayla"));
    await vi.waitFor(() => expect(callsTo("pipeline.cancel")).toHaveLength(1));
    await vi.waitFor(() =>
      expect(screen.queryByText("Dönüşümü iptal et")).not.toBeInTheDocument(),
    );
  });

  it("shows an error toast when pipeline.cancel fails", async () => {
    renderConvert();
    await startRunning();
    invokeMock.mockResolvedValue(rpcErr(-32000, "iptal edilemedi"));
    fireEvent.click(screen.getByRole("button", { name: "İptal" }));
    fireEvent.click(await screen.findByText("Onayla"));
    await vi.waitFor(() => expect(screen.getByText(/iptal edilemedi/)).toBeInTheDocument());
  });

  // --- Donustur akisi: basari bandi ve sonrasindaki islemler ---
  it("renders the result band with action buttons after a successful conversion", async () => {
    renderConvert();
    await startRunning();
    await finishSuccess();
    expect(screen.getByText("/out/sonuc.pkg.tar.zst")).toBeInTheDocument();
    expect(screen.getByText("Başarılı")).toBeInTheDocument();
    for (const label of ["Kur", "Klasörü Aç", "Yolu Kopyala", "OCI", "Bağımlılık grafiği"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByText(/donusum bitti/)).toBeInTheDocument();
  });

  it("opens the output folder and copies the path to the clipboard", async () => {
    const writeText = mockClipboard(() => Promise.resolve());
    try {
      renderConvert();
      await startRunning();
      await finishSuccess();
      fireEvent.click(screen.getByRole("button", { name: "Klasörü Aç" }));
      await vi.waitFor(() => expect(callsTo("system.open_path")).toHaveLength(1));
      expect(callsTo("system.open_path")[0][1]).toEqual(
        expect.objectContaining({ params: { path: "/out/sonuc.pkg.tar.zst" } }),
      );
      fireEvent.click(screen.getByRole("button", { name: "Yolu Kopyala" }));
      await vi.waitFor(() =>
        expect(writeText).toHaveBeenCalledWith("/out/sonuc.pkg.tar.zst"),
      );
      await vi.waitFor(() =>
        expect(screen.getByText("Yol panoya kopyalandı")).toBeInTheDocument(),
      );
    } finally {
      clearClipboard();
    }
  });

  it("toasts when the clipboard write fails", async () => {
    mockClipboard(() => Promise.reject(new Error("pano yok")));
    try {
      renderConvert();
      await startRunning();
      await finishSuccess();
      fireEvent.click(screen.getByRole("button", { name: "Yolu Kopyala" }));
      await vi.waitFor(() =>
        expect(screen.getByText("Yol kopyalanamadı")).toBeInTheDocument(),
      );
    } finally {
      clearClipboard();
    }
  });

  it("starts the OCI export and toasts", async () => {
    renderConvert();
    await startRunning();
    await finishSuccess();
    fireEvent.click(screen.getByRole("button", { name: "OCI" }));
    await vi.waitFor(() => expect(callsTo("export.oci")).toHaveLength(1));
    expect(callsTo("export.oci")[0][1]).toEqual(
      expect.objectContaining({ params: { pkg_path: "/out/sonuc.pkg.tar.zst" } }),
    );
    await vi.waitFor(() => expect(screen.getByText(/OCI imajı/)).toBeInTheDocument());
  });

  it("surfaces RPC errors from post-conversion actions as toasts", async () => {
    renderConvert();
    await startRunning();
    await finishSuccess();
    invokeMock.mockImplementation((_cmd: string, req: RpcReq) =>
      Promise.resolve(rpcErr(-9, `${req.method} patladi`)),
    );
    fireEvent.click(screen.getByRole("button", { name: "Klasörü Aç" }));
    await vi.waitFor(() =>
      expect(screen.getByText(/system.open_path patladi/)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "OCI" }));
    await vi.waitFor(() =>
      expect(screen.getByText(/export.oci patladi/)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Bağımlılık grafiği" }));
    await vi.waitFor(() =>
      expect(screen.getByText(/graph.build patladi/)).toBeInTheDocument(),
    );
    // Graf yuklenemedi ama buton yeniden etkinlesti.
    expect(screen.getByRole("button", { name: "Bağımlılık grafiği" })).toBeEnabled();
  });

  it("builds and renders the dependency graph on graph_done", async () => {
    renderConvert();
    await startRunning();
    await finishSuccess();
    fireEvent.click(screen.getByRole("button", { name: "Bağımlılık grafiği" }));
    await vi.waitFor(() => expect(callsTo("graph.build")).toHaveLength(1));
    expect(callsTo("graph.build")[0][1]).toEqual(
      expect.objectContaining({ params: { pkg_path: "/out/sonuc.pkg.tar.zst" } }),
    );
    act(() => emit("event/graph_done", { ok: true, result: GRAPH_DATA }));
    await vi.waitFor(() => expect(screen.getByText("Toplam: 2")).toBeInTheDocument());
    expect(screen.getByRole("img")).toBeInTheDocument();
    expect(screen.getByText("ana")).toBeInTheDocument();
    expect(screen.getByText("bag")).toBeInTheDocument();
  });

  it("toasts when graph_done reports failure", async () => {
    renderConvert();
    await startRunning();
    await finishSuccess();
    fireEvent.click(screen.getByRole("button", { name: "Bağımlılık grafiği" }));
    await vi.waitFor(() => expect(callsTo("graph.build")).toHaveLength(1));
    act(() => emit("event/graph_done", { ok: false, error: "cizilemedi" }));
    await vi.waitFor(() => expect(screen.getByText("cizilemedi")).toBeInTheDocument());
    // Hata metni yoksa varsayilan convGraphFail mesaji gosterilir.
    fireEvent.click(screen.getByRole("button", { name: "Bağımlılık grafiği" }));
    await vi.waitFor(() => expect(callsTo("graph.build")).toHaveLength(2));
    act(() => emit("event/graph_done", { ok: false }));
    await vi.waitFor(() =>
      expect(screen.getByText("Grafik oluşturulamadı")).toBeInTheDocument(),
    );
  });

  it("installs the output package and toasts the backend message", async () => {
    renderConvert();
    await startRunning();
    await finishSuccess();
    fireEvent.click(screen.getByRole("button", { name: "Kur" }));
    await vi.waitFor(() => expect(callsTo("system.install_pkg")).toHaveLength(1));
    expect(callsTo("system.install_pkg")[0][1]).toEqual(
      expect.objectContaining({ params: { pkg_path: "/out/sonuc.pkg.tar.zst" } }),
    );
    act(() =>
      emit("event/install_done", { ok: true, result: { ok: true, message: "paket kuruldu" } }),
    );
    await vi.waitFor(() => expect(screen.getByText("paket kuruldu")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Kur" })).toBeEnabled();
  });

  it("toasts the backend message when the install result is not ok", async () => {
    renderConvert();
    await startRunning();
    await finishSuccess();
    fireEvent.click(screen.getByRole("button", { name: "Kur" }));
    await vi.waitFor(() => expect(callsTo("system.install_pkg")).toHaveLength(1));
    act(() =>
      emit("event/install_done", { ok: true, result: { ok: false, message: "imza dogrulanamadi" } }),
    );
    await vi.waitFor(() =>
      expect(screen.getByText("imza dogrulanamadi")).toBeInTheDocument(),
    );
  });

  it("toasts a default message when install_done carries no detail", async () => {
    renderConvert();
    await startRunning();
    await finishSuccess();
    fireEvent.click(screen.getByRole("button", { name: "Kur" }));
    await vi.waitFor(() => expect(callsTo("system.install_pkg")).toHaveLength(1));
    act(() => emit("event/install_done", { ok: false }));
    await vi.waitFor(() =>
      expect(screen.getByText("Kurulum başarısız")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Kur" }));
    await vi.waitFor(() => expect(callsTo("system.install_pkg")).toHaveLength(2));
    act(() => emit("event/install_done", { ok: false, error: "baglanti koptu" }));
    await vi.waitFor(() => expect(screen.getByText("baglanti koptu")).toBeInTheDocument());
  });

  it("re-enables install and toasts when system.install_pkg fails", async () => {
    renderConvert();
    await startRunning();
    await finishSuccess();
    invokeMock.mockResolvedValue(rpcErr(-5, "kurulum baslatilamadi"));
    fireEvent.click(screen.getByRole("button", { name: "Kur" }));
    await vi.waitFor(() =>
      expect(screen.getByText(/kurulum baslatilamadi/)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Kur" })).toBeEnabled();
  });

  // --- Ilerleme / adim gostergesi / ETA ---
  it("shows the preparing label, indeterminate marker and live percent while running", async () => {
    renderConvert();
    await startRunning();
    // Henuz aktif adim yokken "Hazirlaniyor" gosterilir.
    await vi.waitFor(() =>
      expect(screen.getByText("Hazırlanıyor…")).toBeInTheDocument(),
    );
    // "Donusum" etiketi bir kez gostergede vardir; adim aktiflesince ikiye cikar.
    expect(screen.getAllByText("Dönüşüm")).toHaveLength(1);
    act(() => emit("event/step_changed", { step: 3, status: "running" }));
    await vi.waitFor(() => expect(screen.getAllByText("Dönüşüm")).toHaveLength(2));
    // Ilerleme sifirken belirsiz sure isareti gosterilir.
    expect(screen.getByText("…")).toBeInTheDocument();
    act(() => emit("event/progress", { value: 42 }));
    await vi.waitFor(() => expect(screen.getByText("42%")).toBeInTheDocument());
    expect(screen.queryByText("…")).not.toBeInTheDocument();
  });

  it("shows elapsed time and an ETA once the conversion has progress", async () => {
    renderConvert();
    await startRunning();
    act(() => emit("event/step_changed", { step: 3, status: "running" }));
    act(() => emit("event/progress", { value: 50 }));
    await vi.waitFor(
      () => expect(screen.getAllByText(/ETA ~\d+ sn/).length).toBeGreaterThan(0),
      { timeout: 4000 },
    );
    expect(screen.getAllByText(/Geçen süre/).length).toBeGreaterThan(0);
  }, 10000);

  // --- Kaynaktan sihirbaz (URL ekle) ---
  it("rejects an empty repo URL in the from-source wizard", async () => {
    renderConvert();
    fireEvent.click(screen.getByText("Kaynaktan"));
    expect(screen.getByText("Kaynaktan PKGBUILD Sihirbazı")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Oluştur"));
    await vi.waitFor(() =>
      expect(screen.getByText("Bir depo URL'si girin")).toBeInTheDocument(),
    );
    expect(callsTo("source.generate")).toHaveLength(0);
  });

  it("generates a PKGBUILD from a repo URL", async () => {
    renderConvert();
    fireEvent.click(screen.getByText("Kaynaktan"));
    fireEvent.change(screen.getByPlaceholderText("https://github.com/user/repo.git"), {
      target: { value: "https://github.com/foo/bar.git" },
    });
    fireEvent.click(screen.getByText("Oluştur"));
    await vi.waitFor(() => expect(callsTo("source.generate")).toHaveLength(1));
    expect(callsTo("source.generate")[0][1]).toEqual(
      expect.objectContaining({ params: { repo_url: "https://github.com/foo/bar.git" } }),
    );
    // Mesgul rozeti once genel etiketi gosterir, sonra adim adim ilerler.
    expect(screen.getByText("Çalışıyor…")).toBeInTheDocument();
    act(() => emit("event/source_progress", { step: "clone" }));
    await vi.waitFor(() =>
      expect(screen.getByText("Depo klonlanıyor…")).toBeInTheDocument(),
    );
    act(() => emit("event/source_progress", { step: "detect" }));
    await vi.waitFor(() =>
      expect(screen.getByText("Build sistemi tespit ediliyor…")).toBeInTheDocument(),
    );
    act(() => emit("event/source_progress", { step: "generate" }));
    await vi.waitFor(() =>
      expect(screen.getByText("PKGBUILD üretiliyor…")).toBeInTheDocument(),
    );
    act(() =>
      emit("event/source_done", {
        ok: true,
        result: {
          ok: true,
          proj_name: "bar",
          build_system: "cmake",
          pkgbuild_path: "/tmp/bar/PKGBUILD",
          pkgbuild_content: "pkgname=bar",
        },
      }),
    );
    await vi.waitFor(() => expect(screen.getByText("pkgname=bar")).toBeInTheDocument());
    expect(screen.getByText(/Build sistemi: cmake/)).toBeInTheDocument();
    expect(screen.getByText("/tmp/bar/PKGBUILD")).toBeInTheDocument();
    expect(screen.queryByText("Çalışıyor…")).not.toBeInTheDocument();
  });

  it("toasts when source generation fails", async () => {
    renderConvert();
    fireEvent.click(screen.getByText("Kaynaktan"));
    const input = screen.getByPlaceholderText("https://github.com/user/repo.git");
    fireEvent.change(input, { target: { value: "https://github.com/x/y.git" } });
    fireEvent.click(screen.getByText("Oluştur"));
    await vi.waitFor(() => expect(callsTo("source.generate")).toHaveLength(1));
    act(() => emit("event/source_done", { ok: false }));
    await vi.waitFor(() =>
      expect(screen.getByText("PKGBUILD oluşturulamadı")).toBeInTheDocument(),
    );
    // Hata mesajli varyant da iletilir.
    fireEvent.click(screen.getByText("Oluştur"));
    await vi.waitFor(() => expect(callsTo("source.generate")).toHaveLength(2));
    act(() => emit("event/source_done", { ok: false, error: "klon basarisiz" }));
    await vi.waitFor(() =>
      expect(screen.getByText("klon basarisiz")).toBeInTheDocument(),
    );
  });

  it("toasts and re-enables the wizard when source.generate errors", async () => {
    invokeMock.mockResolvedValue(rpcErr(-7, "depo klonlanamadi"));
    renderConvert();
    fireEvent.click(screen.getByText("Kaynaktan"));
    fireEvent.change(screen.getByPlaceholderText("https://github.com/user/repo.git"), {
      target: { value: "https://github.com/x/y.git" },
    });
    fireEvent.click(screen.getByText("Oluştur"));
    await vi.waitFor(() =>
      expect(screen.getByText(/depo klonlanamadi/)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Oluştur" })).toBeEnabled();
    expect(screen.queryByText("Çalışıyor…")).not.toBeInTheDocument();
  });

  // --- Toplu sekme (B6 + Faz 9/10) ---
  it("lists batch items with status, priority, message and per-item actions", async () => {
    renderConvert();
    await openBatchTab();
    expect(screen.getByText("sira bekliyor")).toBeInTheDocument();
    expect(screen.getByText("donusturulemedi")).toBeInTheDocument();
    expect(screen.getAllByText(/öncelik \d/)).toHaveLength(4);
    expect(screen.getByText("done")).toBeInTheDocument();
    // Calisan oge: iptal butonu var, kaldir butonu devre disi.
    expect(screen.getByRole("button", { name: "İptal Et a.deb" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "kaldır a.deb" })).toBeDisabled();
    // Bekleyen oge: kaldir butonu etkin, iptal butonu yok.
    expect(screen.getByRole("button", { name: "kaldır b.deb" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "İptal Et b.deb" })).not.toBeInTheDocument();
  });

  it("cancels a running batch item via queue.cancel", async () => {
    renderConvert();
    await openBatchTab();
    fireEvent.click(screen.getByRole("button", { name: "İptal Et a.deb" }));
    await vi.waitFor(() => expect(callsTo("queue.cancel")).toHaveLength(1));
    expect(callsTo("queue.cancel")[0][1]).toEqual(
      expect.objectContaining({ params: { item_id: "/tmp/a.deb" } }),
    );
    // Iptal sonrasi kuyruk yeniden yuklenir.
    await vi.waitFor(() => expect(callsTo("queue.list").length).toBeGreaterThanOrEqual(2));
  });

  it("toasts when queue.cancel fails", async () => {
    renderConvert();
    await openBatchTab();
    invokeMock.mockImplementation((_cmd: string, req: RpcReq) =>
      Promise.resolve(
        req.method === "queue.cancel"
          ? rpcErr(-2, "calisan oge iptal edilemedi")
          : rpcOk(BATCH_ITEMS),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "İptal Et a.deb" }));
    await vi.waitFor(() =>
      expect(screen.getByText(/calisan oge iptal edilemedi/)).toBeInTheDocument(),
    );
  });

  it("raises and lowers batch item priority", async () => {
    renderConvert();
    await openBatchTab();
    fireEvent.click(screen.getByRole("button", { name: "Önceliği artır b.deb" }));
    await vi.waitFor(() => expect(callsTo("queue.priority")).toHaveLength(1));
    expect(callsTo("queue.priority")[0][1]).toEqual(
      expect.objectContaining({ params: { id: "/tmp/b.deb", priority: 2 } }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Önceliği azalt b.deb" }));
    await vi.waitFor(() => expect(callsTo("queue.priority")).toHaveLength(2));
    expect(callsTo("queue.priority")[1][1]).toEqual(
      expect.objectContaining({ params: { id: "/tmp/b.deb", priority: 0 } }),
    );
  });

  it("removes a single batch item, clears the queue and refreshes the list", async () => {
    renderConvert();
    await openBatchTab();
    fireEvent.click(screen.getByRole("button", { name: "kaldır b.deb" }));
    await vi.waitFor(() => expect(callsTo("queue.remove")).toHaveLength(1));
    expect(callsTo("queue.remove")[0][1]).toEqual(
      expect.objectContaining({ params: { id: "/tmp/b.deb" } }),
    );
    fireEvent.click(screen.getByText("Temizle"));
    await vi.waitFor(() => expect(callsTo("queue.clear")).toHaveLength(1));
    const listsBefore = callsTo("queue.list").length;
    fireEvent.click(screen.getByText("Yenile"));
    await vi.waitFor(() =>
      expect(callsTo("queue.list").length).toBeGreaterThan(listsBefore),
    );
  });

  it("filters the batch list and shows the empty state when nothing matches", async () => {
    renderConvert();
    await openBatchTab();
    const filter = screen.getByPlaceholderText("Filtrele…");
    fireEvent.change(filter, { target: { value: "c.de" } });
    await vi.waitFor(() => expect(screen.getByText("c.deb")).toBeInTheDocument());
    expect(screen.queryByText("a.deb")).not.toBeInTheDocument();
    expect(screen.queryByText("b.deb")).not.toBeInTheDocument();
    fireEvent.change(filter, { target: { value: "yok-boyle" } });
    await vi.waitFor(() =>
      expect(
        screen.getByText("Kuyruk boş. Paket dosyalarını yukarı sürükleyin."),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText("c.deb")).not.toBeInTheDocument();
  });

  it("starts the batch queue with the configured parallelism", async () => {
    renderConvert();
    await openBatchTab();
    mockRpc({ "queue.list": rpcOk(BATCH_ITEMS), "queue.start": rpcOk({ started: true }) });
    fireEvent.click(screen.getByText("Toplu Başlat"));
    await vi.waitFor(() => expect(callsTo("queue.start")).toHaveLength(1));
    expect(callsTo("queue.start")[0][1]).toEqual(
      expect.objectContaining({ params: { parallel: 1, install: false } }),
    );
    await vi.waitFor(() => expect(screen.getByText("çalışıyor…")).toBeInTheDocument());
  });

  it("reports why the batch did not start", async () => {
    renderConvert();
    await openBatchTab();
    mockRpc({
      "queue.list": rpcOk(BATCH_ITEMS),
      "queue.start": rpcOk({ started: false, reason: "no pending items" }),
    });
    fireEvent.click(screen.getByText("Toplu Başlat"));
    await vi.waitFor(() =>
      expect(screen.getByText("Bekleyen öğe yok")).toBeInTheDocument(),
    );
    mockRpc({
      "queue.list": rpcOk(BATCH_ITEMS),
      "queue.start": rpcOk({ started: false, reason: "already running" }),
    });
    fireEvent.click(screen.getByText("Toplu Başlat"));
    await vi.waitFor(() =>
      expect(screen.getByText("Zaten çalışıyor")).toBeInTheDocument(),
    );
    await vi.waitFor(() =>
      expect(screen.queryByText("çalışıyor…")).not.toBeInTheDocument(),
    );
  });

  it("honours the parallel input, forces serial install when opted in, resets on queue_done", async () => {
    renderConvert();
    await openBatchTab();
    mockRpc({ "queue.list": rpcOk(BATCH_ITEMS), "queue.start": rpcOk({ started: true }) });
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "3" } });
    fireEvent.click(screen.getByText("Toplu Başlat"));
    await vi.waitFor(() =>
      expect(callsTo("queue.start")[0][1]).toEqual(
        expect.objectContaining({ params: { parallel: 3, install: false } }),
      ),
    );
    // Kuyruk bitti olayi calisma rozetini indirir ve listeyi tazeler.
    const listsBefore = callsTo("queue.list").length;
    act(() => emit("event/queue_done", {}));
    await vi.waitFor(() =>
      expect(callsTo("queue.list").length).toBeGreaterThan(listsBefore),
    );
    await vi.waitFor(() =>
      expect(screen.queryByText("çalışıyor…")).not.toBeInTheDocument(),
    );
    // Kur (seri) secili iken paralellik 1'e sabitlenir.
    fireEvent.click(screen.getByLabelText("Kur (seri)"));
    fireEvent.click(screen.getByText("Toplu Başlat"));
    await vi.waitFor(() =>
      expect(callsTo("queue.start")[1][1]).toEqual(
        expect.objectContaining({ params: { parallel: 1, install: true } }),
      ),
    );
  });

  it("adds browsed files to the batch queue via queue.add", async () => {
    renderConvert();
    await openBatchTab();
    vi.mocked(open).mockResolvedValueOnce(["/tmp/yeni.deb"]);
    fireEvent.click(screen.getByRole("button", { name: "Paket bırakma alanı" }));
    await vi.waitFor(() => expect(callsTo("queue.add")).toHaveLength(1));
    expect(callsTo("queue.add")[0][1]).toEqual(
      expect.objectContaining({ params: { paths: ["/tmp/yeni.deb"] } }),
    );
  });

  it("toasts when the batch queue cannot be loaded", async () => {
    invokeMock.mockImplementation((_cmd: string, req: RpcReq) =>
      Promise.resolve(
        req.method === "queue.list" ? rpcErr(-32000, "kuyruk okunamiyor") : rpcOk({}),
      ),
    );
    renderConvert();
    fireEvent.click(screen.getByText("Toplu"));
    await vi.waitFor(() =>
      expect(screen.getByText(/kuyruk okunamiyor/)).toBeInTheDocument(),
    );
  });

  // --- Uyumluluk raporu: kapatma dali ---
  it("dismisses the compatibility report via pipeline.dismiss", async () => {
    renderConvert();
    await startRunning();
    act(() =>
      emit("event/compatibility_ready", {
        report: {
          overall: "warning",
          grade: "C",
          checks: [{ name: "abi", severity: "warning", message: "supheli sembol", details: [] }],
        },
      }),
    );
    await vi.waitFor(() =>
      expect(screen.getByText(/Uyumluluk Raporu/)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText("Kapat"));
    await vi.waitFor(() => expect(callsTo("pipeline.dismiss")).toHaveLength(1));
    expect(callsTo("pipeline.dismiss")[0][1]).toEqual(
      expect.objectContaining({ params: { message: "" } }),
    );
    await vi.waitFor(() =>
      expect(screen.queryByText(/Uyumluluk Raporu/)).not.toBeInTheDocument(),
    );
  });
});
