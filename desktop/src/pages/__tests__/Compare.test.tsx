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
import { Compare } from "../Compare";
import { ToastProvider } from "../../components/ui/Toast";

async function renderCompare() {
  const r = render(
    <ToastProvider>
      <Compare />
    </ToastProvider>,
  );
  await act(async () => {});
  return r;
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

type CompareDonePayload = { ok: boolean; result?: unknown; error?: string };

/** Kayitli event/compare_done dinleyicisini bulur ve olayi tetikler. */
function emitCompareDone(payload: CompareDonePayload) {
  const calls = vi.mocked(listen).mock.calls as unknown as [
    string,
    (e: { payload: unknown }) => void,
  ][];
  const entry = calls.find(([name]) => name === "event/compare_done");
  if (!entry) throw new Error("event/compare_done dinleyicisi kayitli degil");
  act(() => entry[1]({ payload }));
}

/** Her iki yolu doldurur, karsilastirmayi baslatir ve RPC cagrisini bekler. */
async function startCompare() {
  fireEvent.change(screen.getByPlaceholderText(/eski paket/i), {
    target: { value: "/tmp/eski.pkg.tar.zst" },
  });
  fireEvent.change(screen.getByPlaceholderText(/yeni paket/i), {
    target: { value: "/tmp/yeni.pkg.tar.zst" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Karşılaştır" }));
  await vi.waitFor(() => expect(callsTo("compare.diff")).toHaveLength(1));
  // RPC yanitinin mikro gorev zincirini act icinde bosalt (act uyarisini onler).
  await act(async () => {});
}

/** Tum fark bolumleri dolu SbomDiff; fmtSize'in B ve MB dallarina da dokunur. */
const FULL_DIFF = {
  old_name: "foo",
  old_version: "1.0-1",
  new_name: "foo",
  new_version: "2.0-1",
  added_files: ["/usr/share/yeni.txt"],
  removed_files: ["/usr/share/eski.txt"],
  changed_files: [{ path: "/usr/bin/foo", old_sha256: "aa", new_sha256: "bb" }],
  changed_deps: [],
  added_deps: ["libyeni"],
  removed_deps: ["libeski"],
  version_changes: [{ dep: "glibc", old: "2.38", new: "2.39" }],
  old_total_files: 10,
  new_total_files: 12,
  old_total_size: 500,
  new_total_size: 3 * 1024 * 1024,
};

/** Hic fark icermeyen SbomDiff; noChange rozetini ve KB boyut dalini kapsar. */
const SAME_DIFF = {
  old_name: "bar",
  old_version: "1.0-1",
  new_name: "bar",
  new_version: "1.0-1",
  added_files: [],
  removed_files: [],
  changed_files: [],
  changed_deps: [],
  added_deps: [],
  removed_deps: [],
  version_changes: [],
  old_total_files: 5,
  new_total_files: 5,
  old_total_size: 2048,
  new_total_size: 2048,
};

const ADDED_ONLY = { ...SAME_DIFF, added_files: ["/usr/yeni"], new_total_files: 6 };
const REMOVED_ONLY = { ...SAME_DIFF, removed_files: ["/usr/eski"], new_total_files: 4 };

describe("Compare page", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    vi.mocked(listen).mockClear();
  });

  it("renders two package path inputs", async () => {
    await renderCompare();
    expect(screen.getByPlaceholderText(/eski paket/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/yeni paket/i)).toBeInTheDocument();
  });

  it("has a compare button", async () => {
    await renderCompare();
    expect(screen.getByText("Karşılaştır")).toBeInTheDocument();
  });

  it("calls compare.diff when both paths set", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { started: true } });
    await renderCompare();
    fireEvent.change(screen.getByPlaceholderText(/eski paket/i), { target: { value: "/tmp/a.pkg.tar.zst" } });
    fireEvent.change(screen.getByPlaceholderText(/yeni paket/i), { target: { value: "/tmp/b.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Karşılaştır"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "compare.diff" }),
      ),
    );
  });

  it("shows the empty state before any comparison", async () => {
    await renderCompare();
    expect(screen.getByText("Henüz karşılaştırma yok")).toBeInTheDocument();
    expect(screen.getByText(/İki paket seçip/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Karşılaştır" })).toBeEnabled();
  });

  it("requires both paths before calling compare.diff", async () => {
    await renderCompare();
    const button = screen.getByRole("button", { name: "Karşılaştır" });
    // Ikisi de bos: kisa devre, RPC yok.
    fireEvent.click(button);
    await vi.waitFor(() =>
      expect(screen.getByText("İki paket yolu da gerekli")).toBeInTheDocument(),
    );
    // Yalnizca eski yol dolu.
    fireEvent.change(screen.getByPlaceholderText(/eski paket/i), {
      target: { value: "/tmp/eski.pkg.tar.zst" },
    });
    fireEvent.click(button);
    // Yeni yol bosluklardan ibaret.
    fireEvent.change(screen.getByPlaceholderText(/yeni paket/i), {
      target: { value: "   " },
    });
    fireEvent.click(button);
    await vi.waitFor(() =>
      expect(screen.getAllByText("İki paket yolu da gerekli")).toHaveLength(3),
    );
    expect(callsTo("compare.diff")).toHaveLength(0);
  });

  it("toasts the RPC error and re-enables when compare.diff fails", async () => {
    invokeMock.mockResolvedValue(rpcErr(-32000, "sbom okunamadi"));
    await renderCompare();
    await startCompare();
    await vi.waitFor(() =>
      expect(screen.getByText(/-32000: sbom okunamadi/)).toBeInTheDocument(),
    );
    // Mesguliyet kalkar, bos durum geri gelir.
    expect(screen.getByRole("button", { name: "Karşılaştır" })).toBeEnabled();
    expect(screen.getByText("Henüz karşılaştırma yok")).toBeInTheDocument();
  });

  it("disables the button and hides the empty state while comparing", async () => {
    let resolveInvoke!: (v: unknown) => void;
    invokeMock.mockReturnValue(new Promise((r) => { resolveInvoke = r; }));
    await renderCompare();
    fireEvent.change(screen.getByPlaceholderText(/eski paket/i), {
      target: { value: "/tmp/eski.pkg.tar.zst" },
    });
    fireEvent.change(screen.getByPlaceholderText(/yeni paket/i), {
      target: { value: "/tmp/yeni.pkg.tar.zst" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Karşılaştır" }));
    await vi.waitFor(() =>
      expect(screen.getByRole("button", { name: "Karşılaştır" })).toBeDisabled(),
    );
    expect(screen.queryByText("Henüz karşılaştırma yok")).not.toBeInTheDocument();
    // Mesguliyet dondurucusu (Loader2) gosterilir.
    expect(document.querySelector(".animate-spin")).not.toBeNull();
    // Yaniti coz ve olayla tamamla; buton yeniden etkinlesir.
    resolveInvoke(rpcOk({ started: true }));
    await vi.waitFor(() => expect(callsTo("compare.diff")).toHaveLength(1));
    emitCompareDone({ ok: true, result: SAME_DIFF });
    await vi.waitFor(() =>
      expect(screen.getByRole("button", { name: "Karşılaştır" })).toBeEnabled(),
    );
  });

  it("renders the full diff report on compare_done success", async () => {
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderCompare();
    await startCompare();
    emitCompareDone({ ok: true, result: FULL_DIFF });
    await vi.waitFor(() =>
      expect(screen.queryByText("Henüz karşılaştırma yok")).not.toBeInTheDocument(),
    );
    // Baslik: eski -> yeni ad/surum.
    expect(screen.getByText("foo 1.0-1")).toBeInTheDocument();
    expect(screen.getByText("foo 2.0-1")).toBeInTheDocument();
    // Istatistik kartlari: dosya sayisi, boyut (fmtSize B ve MB dallari), eklenen/silinen.
    expect(screen.getByText("10 → 12")).toBeInTheDocument();
    expect(screen.getByText("500 B → 3.0 MB")).toBeInTheDocument();
    expect(screen.getByText("+1")).toBeInTheDocument();
    expect(screen.getByText("-1")).toBeInTheDocument();
    // Bu diff'te "fark yok" rozeti gorunmez.
    expect(screen.queryByText("Fark yok, paketler aynı")).not.toBeInTheDocument();
    // Yeni / kaldirilan bagimlilik rozetleri.
    expect(screen.getByText("Yeni bağımlılıklar")).toBeInTheDocument();
    expect(screen.getByText("libyeni")).toBeInTheDocument();
    expect(screen.getByText("Kaldırılan bağımlılıklar")).toBeInTheDocument();
    expect(screen.getByText("libeski")).toBeInTheDocument();
    // Versiyon degisikligi satiri.
    expect(screen.getByText("Versiyon değişiklikleri")).toBeInTheDocument();
    const vcRow = screen.getByText("glibc").closest("div");
    expect(vcRow).toHaveTextContent("glibc: 2.38 → 2.39");
    // Degisen dosya listesi.
    expect(screen.getByText("Değişen dosyalar (1)")).toBeInTheDocument();
    expect(screen.getByText("/usr/bin/foo")).toBeInTheDocument();
    // Eklenen / silinen dosya sutunlari.
    expect(screen.getByText("Eklenen dosyalar")).toBeInTheDocument();
    expect(screen.getByText("/usr/share/yeni.txt")).toBeInTheDocument();
    expect(screen.getByText("Silinen dosyalar")).toBeInTheDocument();
    expect(screen.getByText("/usr/share/eski.txt")).toBeInTheDocument();
    // Olay sonrasi mesguliyet kalkar.
    expect(screen.getByRole("button", { name: "Karşılaştır" })).toBeEnabled();
  });

  it("shows the no-difference badge when packages are identical", async () => {
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderCompare();
    await startCompare();
    emitCompareDone({ ok: true, result: SAME_DIFF });
    await vi.waitFor(() =>
      expect(screen.getByText("Fark yok, paketler aynı")).toBeInTheDocument(),
    );
    // fmtSize KB dali.
    expect(screen.getByText("2.0 KB → 2.0 KB")).toBeInTheDocument();
    expect(screen.getByText("+0")).toBeInTheDocument();
    expect(screen.getByText("-0")).toBeInTheDocument();
    // Hicbir fark bolumu render edilmez.
    for (const label of [
      "Yeni bağımlılıklar",
      "Kaldırılan bağımlılıklar",
      "Versiyon değişiklikleri",
      "Eklenen dosyalar",
      "Silinen dosyalar",
    ]) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
    expect(screen.queryByText(/^Değişen dosyalar/)).not.toBeInTheDocument();
  });

  it("renders added-only and removed-only file sections separately", async () => {
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderCompare();
    await startCompare();
    // Yalnizca eklenen dosyalar: silinen sutunu render edilmez.
    emitCompareDone({ ok: true, result: ADDED_ONLY });
    await vi.waitFor(() => expect(screen.getByText("/usr/yeni")).toBeInTheDocument());
    expect(screen.getByText("Eklenen dosyalar")).toBeInTheDocument();
    expect(screen.queryByText("Silinen dosyalar")).not.toBeInTheDocument();
    // Yalnizca silinen dosyalar: eklenen sutunu render edilmez.
    emitCompareDone({ ok: true, result: REMOVED_ONLY });
    await vi.waitFor(() => expect(screen.getByText("/usr/eski")).toBeInTheDocument());
    expect(screen.getByText("Silinen dosyalar")).toBeInTheDocument();
    expect(screen.queryByText("Eklenen dosyalar")).not.toBeInTheDocument();
  });

  it("toasts the backend error when compare_done reports failure", async () => {
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderCompare();
    await startCompare();
    emitCompareDone({ ok: false, error: "sbom bozuk" });
    await vi.waitFor(() => expect(screen.getByText("sbom bozuk")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Karşılaştır" })).toBeEnabled();
    expect(screen.getByText("Henüz karşılaştırma yok")).toBeInTheDocument();
  });

  it("falls back to the generic failure toast when the event carries no detail", async () => {
    invokeMock.mockResolvedValue(rpcOk({ started: true }));
    await renderCompare();
    await startCompare();
    // ok=false ve error yok: cmpFailToast fallback.
    emitCompareDone({ ok: false });
    await vi.waitFor(() =>
      expect(screen.getByText("Karşılaştırma başarısız")).toBeInTheDocument(),
    );
    // ok=true ama result yok: yine fallback gosterilir.
    fireEvent.click(screen.getByRole("button", { name: "Karşılaştır" }));
    await vi.waitFor(() => expect(callsTo("compare.diff")).toHaveLength(2));
    emitCompareDone({ ok: true });
    await vi.waitFor(() =>
      expect(screen.getAllByText("Karşılaştırma başarısız")).toHaveLength(2),
    );
  });
});
