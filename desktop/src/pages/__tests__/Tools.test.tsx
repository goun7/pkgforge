import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Tools } from "../Tools";
import { ToastProvider } from "../../components/ui/Toast";
import { listen } from "@tauri-apps/api/event";
import { act } from "react";

async function renderTools() {
  const r = render(
    <ToastProvider>
      <Tools />
    </ToastProvider>,
  );
  await act(async () => {});
  return r;
}

// --- RPC response helper'leri ---

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

const SNAP_NONE = { installed: false, active: false, next_run: "", last_run: "" };

describe("Tools page (Feature Tezgahi)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("renders the three tool cards", async () => {
    await renderTools();
    expect(screen.getByText("RPM → DEB")).toBeInTheDocument();
    expect(screen.getByText("ABI Uyumluluk Denetimi")).toBeInTheDocument();
    expect(screen.getByText("Denetim İzi (Audit)")).toBeInTheDocument();
  });

  it("calls tools.rpm_to_deb when path set and clicked", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { started: true } });
    await renderTools();
    fireEvent.change(screen.getByPlaceholderText("/yol/paket.rpm"), {
      target: { value: "/tmp/p.rpm" },
    });
    fireEvent.click(screen.getByText("Dönüştür"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.rpm_to_deb" }),
      ),
    );
  });

  it("calls tools.abi_check when path set and clicked", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: { started: true } });
    await renderTools();
    fireEvent.change(screen.getAllByPlaceholderText("/yol/paket.pkg.tar.zst")[0], {
      target: { value: "/tmp/p.pkg.tar.zst" },
    });
    fireEvent.click(screen.getByText("Tara"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.abi_check" }),
      ),
    );
  });

  it("loads and shows audit report", async () => {
    const audit = {
      total: 2,
      status_counts: { installed: 2 },
      type_counts: { deb: 2 },
      integrity_issues: 0,
      anomalies: 0,
      records: [],
    };
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: audit });
    await renderTools();
    fireEvent.click(screen.getByText("Denetim İzini Yükle"));
    await vi.waitFor(() =>
      expect(screen.getByText(/Toplam 2/)).toBeInTheDocument(),
    );
    expect(screen.getByText("installed: 2")).toBeInTheDocument();
  });

  it("shows toast error for empty rpm path", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: {} });
    await renderTools();
    fireEvent.click(screen.getByText("Dönüştür"));
    expect(invokeMock).not.toHaveBeenCalledWith(
      "rpc_call",
      expect.objectContaining({ method: "tools.rpm_to_deb" }),
    );
  });
});

describe("Tools page Faz 2 (scan/attest/publish/snapshot)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: {} });
  });

  it("renders the four Faz 2 cards", async () => {
    await renderTools();
    expect(screen.getByText("İmaj Taraması (CVE/Malware)")).toBeInTheDocument();
    expect(screen.getByText("Attestation (SLSA)")).toBeInTheDocument();
    expect(screen.getByText("AUR Yayınla")).toBeInTheDocument();
    expect(screen.getByText("Snapshot Temizliği")).toBeInTheDocument();
  });

  it("loads snapshot status on mount", async () => {
    await renderTools();
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.snapshot_status" }),
      ),
    );
  });

  it("calls tools.scan_image when path set and clicked", async () => {
    await renderTools();
    fireEvent.change(screen.getByPlaceholderText("/yol/imaj.tar"), {
      target: { value: "/tmp/img.tar" },
    });
    fireEvent.click(screen.getByText("İmajı Tara"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.scan_image" }),
      ),
    );
  });

  it("calls tools.attest when path set and clicked", async () => {
    await renderTools();
    const inputs = screen.getAllByPlaceholderText("/yol/paket.pkg.tar.zst");
    fireEvent.change(inputs[1], { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Attestasyon Üret"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.attest" }),
      ),
    );
  });

  it("calls tools.publish when path set and clicked", async () => {
    await renderTools();
    const inputs = screen.getAllByPlaceholderText("/yol/paket.pkg.tar.zst");
    fireEvent.change(inputs[2], { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("AUR Paketi Hazırla"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.publish" }),
      ),
    );
  });

  it("calls tools.snapshot_install when clicked", async () => {
    await renderTools();
    fireEvent.click(screen.getByText("Servisi Kur"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.snapshot_install" }),
      ),
    );
  });
});

describe("Tools page push-event done handlers", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    listenMock.mockClear();
    mockRpc({ "tools.snapshot_status": rpcOk(SNAP_NONE) });
  });

  it("rpm_to_deb_done success renders result badge, message and deb path", async () => {
    await renderTools();
    fireEvent.change(screen.getByPlaceholderText("/yol/paket.rpm"), {
      target: { value: "/tmp/p.rpm" },
    });
    fireEvent.click(screen.getByText("Dönüştür"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "tools.rpm_to_deb", params: { rpm: "/tmp/p.rpm" } }),
      ),
    );
    expect(screen.getByText("Dönüştür").closest("button")).toBeDisabled();
    await vi.waitFor(() => expect(listening("event/rpm_to_deb_done")).toBe(true), { timeout: 5000 });
    emit("event/rpm_to_deb_done", {
      ok: true,
      result: { ok: true, message: "donusum tamamlandi", deb_path: "/tmp/p.deb" },
    });
    expect(await screen.findByText("BAŞARILI", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText(/donusum tamamlandi/)).toBeInTheDocument();
    expect(screen.getByText((c) => c.includes("-> /tmp/p.deb"))).toBeInTheDocument();
    expect(screen.getByText("Dönüştür").closest("button")).toBeEnabled();
  });

  it("rpm_to_deb_done failed result shows HATA badge without deb path", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/rpm_to_deb_done")).toBe(true), { timeout: 5000 });
    emit("event/rpm_to_deb_done", {
      ok: true,
      result: { ok: false, message: "cekirdek uyumsuz", deb_path: null },
    });
    expect(await screen.findByText("HATA", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText(/cekirdek uyumsuz/)).toBeInTheDocument();
    expect(screen.queryByText(/->/)).not.toBeInTheDocument();
  });

  it("rpm_to_deb_done error payload shows error toast (custom then fallback)", async () => {
    await renderTools();
    fireEvent.change(screen.getByPlaceholderText("/yol/paket.rpm"), {
      target: { value: "/tmp/p.rpm" },
    });
    fireEvent.click(screen.getByText("Dönüştür"));
    await vi.waitFor(() => expect(listening("event/rpm_to_deb_done")).toBe(true), { timeout: 5000 });
    await act(async () => emit("event/rpm_to_deb_done", { ok: false, error: "disk dolu" }));
    expect(await screen.findByText("disk dolu", {}, { timeout: 5000 })).toBeInTheDocument();
    await act(async () => emit("event/rpm_to_deb_done", { ok: false }));
    expect(await screen.findByText("RPM dönüşümü başarısız", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("Dönüştür").closest("button")).toBeEnabled();
  });

  it("abi_check_done passed report renders UYUMLU badge and summary", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/abi_check_done")).toBe(true), { timeout: 5000 });
    emit("event/abi_check_done", {
      ok: true,
      result: {
        binary_count: 2, checked_symbols: 10, mismatches: [], missing_libs: [],
        namcap_available: false, namcap_results: [], passed: true, error_count: 0,
        summary: "tum semboller uyumlu",
      },
    });
    expect(await screen.findByText("UYUMLU", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("tum semboller uyumlu")).toBeInTheDocument();
  });

  it("abi_check_done failing report shows issue count badge", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/abi_check_done")).toBe(true), { timeout: 5000 });
    emit("event/abi_check_done", {
      ok: true,
      result: {
        binary_count: 2, checked_symbols: 10, mismatches: [], missing_libs: [],
        namcap_available: false, namcap_results: [], passed: false, error_count: 2,
        summary: "2 uyumsuz sembol",
      },
    });
    expect(await screen.findByText("2 SORUN", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("2 uyumsuz sembol")).toBeInTheDocument();
  });

  it("abi_check_done error payload shows fallback toast", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/abi_check_done")).toBe(true), { timeout: 5000 });
    await act(async () => emit("event/abi_check_done", { ok: false }));
    expect(await screen.findByText("ABI taraması başarısız", {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it("scan_image_done clean image renders TEMIZ badge and detail", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/scan_image_done")).toBe(true), { timeout: 5000 });
    emit("event/scan_image_done", {
      ok: true,
      result: {
        clean: true, tools: { trivy: true, grype: true, clamscan: false },
        findings: [], detail: "imaj temiz bulundu",
      },
    });
    expect(await screen.findByText("TEMİZ", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("imaj temiz bulundu")).toBeInTheDocument();
  });

  it("scan_image_done findings render count badge and finding lines", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/scan_image_done")).toBe(true), { timeout: 5000 });
    emit("event/scan_image_done", {
      ok: true,
      result: {
        clean: false, tools: { trivy: true, grype: true, clamscan: false },
        findings: [
          { tool: "trivy", severity: "HIGH", line: "CVE-2024-1 libx" },
          { tool: "grype", severity: "LOW", line: "CVE-2024-2 liby" },
        ],
        detail: "2 bulgu bulundu",
      },
    });
    expect(await screen.findByText("2 BULGU", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText((c) => c.includes("[trivy/HIGH] CVE-2024-1 libx"))).toBeInTheDocument();
    expect(screen.getByText((c) => c.includes("[grype/LOW] CVE-2024-2 liby"))).toBeInTheDocument();
  });

  it("scan_image_done error payload shows custom toast", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/scan_image_done")).toBe(true), { timeout: 5000 });
    await act(async () => emit("event/scan_image_done", { ok: false, error: "imaj okunamadi" }));
    expect(await screen.findByText("imaj okunamadi", {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it("attest_done success renders OLUŞTURULDU badge and subject path", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/attest_done")).toBe(true), { timeout: 5000 });
    emit("event/attest_done", {
      ok: true,
      result: { ok: true, subject: "pkg@sha256:abc", attestation_path: "/tmp/p.intoto.json" },
    });
    expect(await screen.findByText("OLUŞTURULDU", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("pkg@sha256:abc → /tmp/p.intoto.json")).toBeInTheDocument();
  });

  it("attest_done failed result shows HATA badge and error text", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/attest_done")).toBe(true), { timeout: 5000 });
    emit("event/attest_done", {
      ok: true,
      result: { ok: false, error: "imza anahtari yok" },
    });
    expect(await screen.findByText("HATA", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("imza anahtari yok")).toBeInTheDocument();
  });

  it("attest_done error payload shows fallback toast", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/attest_done")).toBe(true), { timeout: 5000 });
    await act(async () => emit("event/attest_done", { ok: false }));
    expect(await screen.findByText("Attestasyon başarısız", {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it("publish_done success renders HAZIR badge and PKGBUILD path", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/publish_done")).toBe(true), { timeout: 5000 });
    emit("event/publish_done", {
      ok: true,
      result: { ok: true, message: "AUR paketi hazir", pkgbuild: "/tmp/aur/PKGBUILD", pushed: false },
    });
    expect(await screen.findByText("HAZIR", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("AUR paketi hazir")).toBeInTheDocument();
    expect(screen.getByText((c) => c.includes("PKGBUILD: /tmp/aur/PKGBUILD"))).toBeInTheDocument();
  });

  it("publish_done failed result shows HATA badge without PKGBUILD", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/publish_done")).toBe(true), { timeout: 5000 });
    emit("event/publish_done", {
      ok: true,
      result: { ok: false, message: "surum cakismasi", pushed: false },
    });
    expect(await screen.findByText("HATA", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("surum cakismasi")).toBeInTheDocument();
    expect(screen.queryByText(/PKGBUILD:/)).not.toBeInTheDocument();
  });

  it("publish_done error payload shows custom toast", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/publish_done")).toBe(true), { timeout: 5000 });
    await act(async () => emit("event/publish_done", { ok: false, error: "aur erisilemedi" }));
    expect(await screen.findByText("aur erisilemedi", {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it("snapshot_done success toasts the message and reloads status", async () => {
    await renderTools();
    await vi.waitFor(() => expect(methodCalls("tools.snapshot_status")).toBe(1), { timeout: 5000 });
    await vi.waitFor(() => expect(listening("event/snapshot_done")).toBe(true), { timeout: 5000 });
    await act(async () => emit("event/snapshot_done", { ok: true, result: { ok: true, message: "Temizlik tamamlandi" } }));
    expect(await screen.findByText("Temizlik tamamlandi", {}, { timeout: 5000 })).toBeInTheDocument();
    await vi.waitFor(() => expect(methodCalls("tools.snapshot_status")).toBe(2), { timeout: 5000 });
  });

  it("snapshot_done failed result toasts its message", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/snapshot_done")).toBe(true), { timeout: 5000 });
    await act(async () => emit("event/snapshot_done", { ok: true, result: { ok: false, message: "servis calismiyor" } }));
    expect(await screen.findByText("servis calismiyor", {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it("snapshot_done error payload falls back to generic toast", async () => {
    await renderTools();
    await vi.waitFor(() => expect(listening("event/snapshot_done")).toBe(true), { timeout: 5000 });
    await act(async () => emit("event/snapshot_done", { ok: false, error: "beklenmeyen hata" }));
    expect(await screen.findByText("beklenmeyen hata", {}, { timeout: 5000 })).toBeInTheDocument();
    await act(async () => emit("event/snapshot_done", { ok: false }));
    expect(await screen.findByText("Snapshot işlemi başarısız", {}, { timeout: 5000 })).toBeInTheDocument();
  });
});

describe("Tools page handler error paths and snapshot status branches", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    listenMock.mockClear();
  });

  it("handleRpm RPC error toasts the message and re-enables the button", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "tools.rpm_to_deb": rpcErr(-32000, "rpm okunamadi"),
    });
    await renderTools();
    fireEvent.change(screen.getByPlaceholderText("/yol/paket.rpm"), {
      target: { value: "/tmp/p.rpm" },
    });
    fireEvent.click(screen.getByText("Dönüştür"));
    expect(await screen.findByText("-32000: rpm okunamadi", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("Dönüştür").closest("button")).toBeEnabled();
  });

  it("handleAbi RPC error toasts the message", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "tools.abi_check": rpcErr(-32001, "abi taranamadi"),
    });
    await renderTools();
    fireEvent.change(screen.getAllByPlaceholderText("/yol/paket.pkg.tar.zst")[0], {
      target: { value: "/tmp/p.pkg.tar.zst" },
    });
    fireEvent.click(screen.getByText("Tara"));
    expect(await screen.findByText("-32001: abi taranamadi", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("Tara").closest("button")).toBeEnabled();
  });

  it("handleAudit RPC error toasts the message", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "tools.audit": rpcErr(-1, "audit yuklenemedi"),
    });
    await renderTools();
    fireEvent.click(screen.getByText("Denetim İzini Yükle"));
    expect(await screen.findByText("-1: audit yuklenemedi", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("Denetim İzini Yükle").closest("button")).toBeEnabled();
  });

  it("handleScan RPC error toasts the message", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "tools.scan_image": rpcErr(-32002, "imaj taranamadi"),
    });
    await renderTools();
    fireEvent.change(screen.getByPlaceholderText("/yol/imaj.tar"), {
      target: { value: "/tmp/img.tar" },
    });
    fireEvent.click(screen.getByText("İmajı Tara"));
    expect(await screen.findByText("-32002: imaj taranamadi", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("İmajı Tara").closest("button")).toBeEnabled();
  });

  it("handleAttest RPC error toasts the message", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "tools.attest": rpcErr(-32003, "attest uretilemedi"),
    });
    await renderTools();
    const inputs = screen.getAllByPlaceholderText("/yol/paket.pkg.tar.zst");
    fireEvent.change(inputs[1], { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Attestasyon Üret"));
    expect(await screen.findByText("-32003: attest uretilemedi", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("Attestasyon Üret").closest("button")).toBeEnabled();
  });

  it("handlePublish RPC error toasts the message", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "tools.publish": rpcErr(-32004, "yayin hazirlanamadi"),
    });
    await renderTools();
    const inputs = screen.getAllByPlaceholderText("/yol/paket.pkg.tar.zst");
    fireEvent.change(inputs[2], { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("AUR Paketi Hazırla"));
    expect(await screen.findByText("-32004: yayin hazirlanamadi", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("AUR Paketi Hazırla").closest("button")).toBeEnabled();
  });

  it("empty abi path toasts and skips the RPC call", async () => {
    mockRpc({ "tools.snapshot_status": rpcOk(SNAP_NONE) });
    await renderTools();
    fireEvent.click(screen.getByText("Tara"));
    expect(await screen.findByText("Paket yolu gerekli", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(methodCalls("tools.abi_check")).toBe(0);
  });

  it("empty scan path toasts the translated message and skips the RPC call", async () => {
    mockRpc({ "tools.snapshot_status": rpcOk(SNAP_NONE) });
    await renderTools();
    fireEvent.click(screen.getByText("İmajı Tara"));
    expect(await screen.findByText("İmaj yolu gerekli", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(methodCalls("tools.scan_image")).toBe(0);
  });

  it("empty attest path toasts and skips the RPC call", async () => {
    mockRpc({ "tools.snapshot_status": rpcOk(SNAP_NONE) });
    await renderTools();
    fireEvent.click(screen.getByText("Attestasyon Üret"));
    expect(await screen.findByText("Paket yolu gerekli", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(methodCalls("tools.attest")).toBe(0);
  });

  it("empty publish path toasts and skips the RPC call", async () => {
    mockRpc({ "tools.snapshot_status": rpcOk(SNAP_NONE) });
    await renderTools();
    fireEvent.click(screen.getByText("AUR Paketi Hazırla"));
    expect(await screen.findByText("Paket yolu gerekli", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(methodCalls("tools.publish")).toBe(0);
  });

  it("shows installed+active snapshot status with next run", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk({
        installed: true, active: true, next_run: "2026-02-01 03:00", last_run: "",
      }),
    });
    await renderTools();
    expect(
      await screen.findByText(
        (c) => c.includes("Servis kurulu — Aktif | Sıradaki: 2026-02-01 03:00"),
        {},
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
  });

  it("shows installed but stopped snapshot status", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk({ installed: true, active: false, next_run: "", last_run: "" }),
    });
    await renderTools();
    expect(
      await screen.findByText("Servis kurulu — Durdurulmuş", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  it("shows not-installed snapshot status", async () => {
    mockRpc({ "tools.snapshot_status": rpcOk(SNAP_NONE) });
    await renderTools();
    expect(
      await screen.findByText("Snapshot temizlik servisi kurulu değil", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  it("silently ignores a failing snapshot status load", async () => {
    invokeMock.mockRejectedValue(new Error("sidecar kopuk"));
    await renderTools();
    await vi.waitFor(() => expect(methodCalls("tools.snapshot_status")).toBe(1), { timeout: 5000 });
    expect(screen.queryByText(/Servis kurulu/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Snapshot temizlik servisi/)).not.toBeInTheDocument();
  });

  it("refresh button reloads snapshot status", async () => {
    mockRpc({ "tools.snapshot_status": rpcOk(SNAP_NONE) });
    await renderTools();
    await vi.waitFor(() => expect(methodCalls("tools.snapshot_status")).toBe(1), { timeout: 5000 });
    fireEvent.click(screen.getByText("Yenile"));
    await vi.waitFor(() => expect(methodCalls("tools.snapshot_status")).toBe(2), { timeout: 5000 });
    await act(async () => {});
  });

  it("remove service button calls tools.snapshot_remove", async () => {
    mockRpc({ "tools.snapshot_status": rpcOk(SNAP_NONE) });
    await renderTools();
    fireEvent.click(screen.getByText("Servisi Kaldır"));
    await vi.waitFor(() => expect(methodCalls("tools.snapshot_remove")).toBe(1), { timeout: 5000 });
    await act(async () => {});
  });

  it("snapshot_install RPC error toasts and re-enables the button", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "tools.snapshot_install": rpcErr(-2, "servis kurulamadi"),
    });
    await renderTools();
    fireEvent.click(screen.getByText("Servisi Kur"));
    expect(await screen.findByText("-2: servis kurulamadi", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("Servisi Kur").closest("button")).toBeEnabled();
  });
});

describe("Tools page Kurulum Provasi (install.rehearse)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    listenMock.mockClear();
    mockRpc({ "tools.snapshot_status": rpcOk(SNAP_NONE) });
  });

  /** Prova karti, pkg.tar.zst placeholder'li dorduncu (son) input'i kullanir. */
  function rehearseInput(): HTMLElement {
    const inputs = screen.getAllByPlaceholderText("/yol/paket.pkg.tar.zst");
    return inputs[inputs.length - 1];
  }

  it("renders the rehearsal card with description and run button", async () => {
    await renderTools();
    expect(screen.getByText("Kurulum Provası")).toBeInTheDocument();
    expect(
      screen.getByText("Paketi sisteme dokunmadan tek kullanımlık bir konteynerde kurmayı dener."),
    ).toBeInTheDocument();
    expect(screen.getByText("Prova Et")).toBeInTheDocument();
    await act(async () => {});
  });

  it("empty rehearsal path toasts and skips the RPC call", async () => {
    await renderTools();
    fireEvent.click(screen.getByText("Prova Et"));
    expect(
      await screen.findByText("Prova için bir paket yolu girin", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(methodCalls("install.rehearse")).toBe(0);
  });

  it("successful rehearsal shows file count, runtime and file list", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "install.rehearse": rpcOk({
        ok: true, available: true, runtime: "distrobox 1.4",
        file_count: 3, files: ["/usr/bin/a", "/usr/lib/b.so", "/usr/share/c"],
      }),
    });
    await renderTools();
    fireEvent.change(rehearseInput(), { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Prova Et"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({
          method: "install.rehearse",
          params: { package_path: "/tmp/p.pkg.tar.zst" },
        }),
      ),
    { timeout: 5000 });
    expect(await screen.findByText("3 kurulacak dosya", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("distrobox 1.4")).toBeInTheDocument();
    expect(screen.getByText("/usr/bin/a")).toBeInTheDocument();
    expect(screen.getByText("/usr/lib/b.so")).toBeInTheDocument();
    expect(screen.getByText("/usr/share/c")).toBeInTheDocument();
    expect(screen.getByText("Prova Et").closest("button")).toBeEnabled();
  });

  it("successful rehearsal without details falls back to zero file count", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "install.rehearse": rpcOk({ ok: true, available: true }),
    });
    await renderTools();
    fireEvent.change(rehearseInput(), { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Prova Et"));
    expect(await screen.findByText("0 kurulacak dosya", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("unavailable rehearsal shows reason and hint", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "install.rehearse": rpcOk({
        ok: false, available: false, reason: "konteyner runtime yok", hint: "distrobox kurun",
      }),
    });
    await renderTools();
    fireEvent.change(rehearseInput(), { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Prova Et"));
    expect(
      await screen.findByText("konteyner runtime yok — distrobox kurun", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  it("unavailable rehearsal without reason falls back to the generic message", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "install.rehearse": rpcOk({ ok: false, available: false }),
    });
    await renderTools();
    fireEvent.change(rehearseInput(), { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Prova Et"));
    expect(
      await screen.findByText("Konteyner runtime bulunamadı", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  it("failed rehearsal shows the failure reason", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "install.rehearse": rpcOk({ ok: false, available: true, reason: "bagimlilik cozulemedi" }),
    });
    await renderTools();
    fireEvent.change(rehearseInput(), { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Prova Et"));
    expect(
      await screen.findByText("bagimlilik cozulemedi", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  it("failed rehearsal without reason falls back to the generic failure", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "install.rehearse": rpcOk({ ok: false, available: true }),
    });
    await renderTools();
    fireEvent.change(rehearseInput(), { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Prova Et"));
    expect(await screen.findByText("Prova başarısız", {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it("rehearsal RPC error toasts and re-enables the button", async () => {
    mockRpc({
      "tools.snapshot_status": rpcOk(SNAP_NONE),
      "install.rehearse": rpcErr(-32601, "konteyner baslatilamadi"),
    });
    await renderTools();
    fireEvent.change(rehearseInput(), { target: { value: "/tmp/p.pkg.tar.zst" } });
    fireEvent.click(screen.getByText("Prova Et"));
    expect(
      await screen.findByText("-32601: konteyner baslatilamadi", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Prova Et").closest("button")).toBeEnabled();
  });
});
