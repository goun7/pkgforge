import { render, screen, fireEvent, within, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

import { Installed } from "../Installed";
import { ToastProvider } from "../../components/ui/Toast";

/** Tek satır üretir — testlerde tekrar tekrar yazmamak için. */
function rec(i: number, name = "p" + i, status = "success") {
  return {
    id: i,
    timestamp: "2026-08-2" + (i % 10) + " 10:0" + (i % 10),
    package_name: name,
    package_type: "deb",
    status,
    original_file: "/tmp/" + name + ".deb",
    source_url: "",
  };
}

function renderInstalled() {
  return render(
    <ToastProvider>
      <Installed />
    </ToastProvider>,
  );
}

describe("Installed — Faz 19b kapsam dalları", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: [rec(1)] });
  });

  it("sıralama: başlığa tıkla → asc→desc döner ve satır sırası değişir", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: [rec(1, "zeta"), rec(2, "alpha")],
    });
    renderInstalled();
    await screen.findByText("zeta");
    const pkgHeader = screen.getByRole("button", { name: /Paket/ });
    // İlk tık: asc sıralama (alpha önce).
    fireEvent.click(pkgHeader);
    const rows = () => Array.from(screen.getAllByRole("row")).slice(1);
    expect(rows()[0].textContent).toContain("alpha");
    // İkinci tık: desc (zeta önce).
    fireEvent.click(pkgHeader);
    expect(rows()[0].textContent).toContain("zeta");
  });

  it("yoğunluk düğmesi Rahat↔Kompakt etiketini değiştirir", async () => {
    renderInstalled();
    // Erişilebilir ad: aria-label 'Tablo yoğunluğu'; içerik Rahat/Kompakt.
    const btn = await screen.findByRole("button", { name: "Tablo yoğunluğu" });
    expect(btn.textContent).toContain("Rahat");
    fireEvent.click(btn);
    expect(btn.textContent).toContain("Kompakt");
  });

  it("CSV ihracı: blob URL oluşturur ve indirme bağlantısını tetikler", async () => {
    const createObjectURL = vi.fn(() => "blob:csv");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, configurable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: revokeObjectURL, configurable: true });
    const clickSpy = vi.fn();
    const origClick = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = clickSpy;
    renderInstalled();
    try {
      fireEvent.click(await screen.findByRole("button", { name: /CSV/i }));
      expect(createObjectURL).toHaveBeenCalled();
      expect(clickSpy).toHaveBeenCalled();
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:csv");
    } finally {
      HTMLAnchorElement.prototype.click = origClick;
    }
  });

  it("sayfalama: 60 kayıtta 'daha fazla' görünür ve kalanları açar", async () => {
    const many = Array.from({ length: 60 }, (_, i) => rec(i + 1, "pkg" + String(i + 1).padStart(3, "0")));
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: many });
    renderInstalled();
    await screen.findByText("pkg001");
    // Varsayılan 50 satır: pkg051 DOM'da değil.
    expect(screen.queryByText("pkg051")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /daha fazla|Daha fazla/i }));
    await screen.findByText("pkg051");
    expect(screen.getByText("pkg060")).toBeInTheDocument();
  });

  it("geçmişi temizle: onay → history.clear + Geri Al toast aksiyonu history.restore", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
      if (payload.method === "history.list") {
        return Promise.resolve({ jsonrpc: "2.0", id: 1, result: [rec(1)] });
      }
      return Promise.resolve({ jsonrpc: "2.0", id: 1, result: null });
    });
    renderInstalled();
    await screen.findByText("p1");
    fireEvent.click(screen.getByRole("button", { name: /Temizle/i }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByText("Onayla"));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "history.clear" }),
      ),
    );
    // Geri Al aksiyonlu başarı toast'u çıktı mı?
    expect(await screen.findByText(/geçmiş temizlendi|Geçmiş temizlendi/i)).toBeInTheDocument();
    const undo = await screen.findByText(/Geri al|Geri Al/i);
    await act(async () => {
      fireEvent.click(undo);
    });
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "history.restore" }),
      ),
    );
  });

  it("rollback: geri al düğmesi history.rollback çağırır; yetki gerekirse bilgi verir", async () => {
    invokeMock.mockImplementation((_cmd: string, payload: { method: string }) => {
      if (payload.method === "history.list") {
        return Promise.resolve({ jsonrpc: "2.0", id: 1, result: [rec(1, "pkgR")] });
      }
      return Promise.resolve({
        jsonrpc: "2.0",
        id: 2,
        result: { requires_privilege: true },
      });
    });
    renderInstalled();
    await screen.findByText("pkgR");
    fireEvent.click(screen.getByLabelText(/Geri al pkgR|Geri Al pkgR/i));
    await vi.waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith(
        "rpc_call",
        expect.objectContaining({ method: "history.rollback" }),
      ),
    );
  });

  it("filtre hiçbiriyle eşleşmezse boş durum gösterilir", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: [rec(1, "alpha")],
    });
    renderInstalled();
    await screen.findByText("alpha");
    fireEvent.change(screen.getByPlaceholderText("Filtrele…"), { target: { value: "yokboyle" } });
    expect(await screen.findByText(/Henüz kayıt yok/)).toBeInTheDocument();
  });

  it("yenile düğmesi history.list'i tekrar çağırır", async () => {
    renderInstalled();
    await screen.findByText("p1");
    const before = invokeMock.mock.calls.filter((c) => c[1]?.method === "history.list").length;
    fireEvent.click(screen.getByRole("button", { name: /Yenile/i }));
    await vi.waitFor(() =>
      expect(
        invokeMock.mock.calls.filter((c) => c[1]?.method === "history.list").length,
      ).toBeGreaterThan(before),
    );
  });
});
