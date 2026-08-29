import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

import { DoctorPanel } from "../DoctorPanel";
import { ToastProvider } from "../ui/Toast";

const healthyReport = {
  version: "2.0.0",
  ok: true,
  tools: { ok: true, missing_required: [], missing_optional: [], debtap: true, pkexec: true, distrobox: false },
  keyring: { ok: true },
  storage: { ok: true, profile: "default" },
  dbus: { ok: true },
  scheduler: { ok: true, tasks: 0 },
};

/** Sorunlu rapor: eksik araclar, string/object probe detaylari, profil/gorev yok. */
const issueReport = {
  version: "2.1.0",
  ok: false,
  tools: { ok: false, missing_required: ["debtap"], missing_optional: ["distrobox"], debtap: false, pkexec: true, distrobox: false },
  keyring: { ok: false, detail: "secret-service unavailable" },
  storage: { ok: false },
  dbus: { ok: true, detail: { bus: "session" } },
  scheduler: { ok: false },
};

/** Opsiyonel profil/gorev alanlari olmayan minimal rapor (falsy dallar). */
const minimalReport = {
  version: "0.9.0",
  ok: true,
  tools: { ok: true, missing_required: [], missing_optional: [], debtap: true, pkexec: true, distrobox: true },
  keyring: { ok: true },
  storage: { ok: true },
  dbus: { ok: true },
  scheduler: { ok: true },
};

/** Kopyalama Markdown'inda tum opsiyonel satirlari iceren rapor. */
const copyFixture = {
  version: "2.1.0",
  ok: false,
  tools: { ok: false, missing_required: ["debtap", "pacman"], missing_optional: ["distrobox"], debtap: false, pkexec: false, distrobox: false },
  keyring: { ok: false },
  storage: { ok: true, profile: "default" },
  dbus: { ok: true },
  scheduler: { ok: true, tasks: 3 },
};

// --- jsdom stub'i: clipboard (Reports.test.tsx deseni) ---
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

function renderPanel() {
  return render(
    <ToastProvider>
      <DoctorPanel />
    </ToastProvider>,
  );
}

describe("DoctorPanel (Faz 10 1.1)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: healthyReport, error: null });
    clipboardWriteText.mockReset();
    clipboardWriteText.mockResolvedValue(undefined);
    installClipboardStub();
  });

  it("runs diagnostics and shows the report", async () => {
    const user = userEvent.setup();
    renderPanel();
    expect(screen.getByText("Sistem Doktoru")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByText(/2\.0\.0/)).toBeInTheDocument();
  });

  it("offers a copy-diagnostics button once a report exists", async () => {
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByRole("button", { name: /Tanıyı kopyala/ })).toBeInTheDocument();
  });

  it("shows a skeleton and disables the run button while busy", async () => {
    let resolveDoctor!: (v: unknown) => void;
    invokeMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveDoctor = resolve;
        }),
    );
    const { container } = renderPanel();
    fireEvent.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    await vi.waitFor(
      () => expect(screen.getByRole("button", { name: /Teşhis Çalıştır/ })).toBeDisabled(),
      { timeout: 5000 },
    );
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
    // Raporu cozundur; iskelet kaybolur, rapor render edilir.
    await act(async () => {
      resolveDoctor({ jsonrpc: "2.0", id: 1, result: healthyReport, error: null });
    });
    expect(await screen.findByText("Sistem sağlıklı")).toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Teşhis Çalıştır/ })).toBeEnabled();
  });

  it("surfaces RPC errors and clears them on a successful re-run", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: null,
      error: { code: -32000, message: "sidecar kapalı" },
    });
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByText("-32000: sidecar kapalı")).toBeInTheDocument();
    // Hata varken rapor ve kopyala butonu yoktur.
    expect(screen.queryByRole("button", { name: /Tanıyı kopyala/ })).not.toBeInTheDocument();
    expect(screen.queryByText("Sistem sağlıklı")).not.toBeInTheDocument();
    // Basarili tekrar calistirma hatayi temizler.
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: healthyReport, error: null });
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByText("Sistem sağlıklı")).toBeInTheDocument();
    expect(screen.queryByText("-32000: sidecar kapalı")).not.toBeInTheDocument();
  });

  it("renders every section of a healthy report", async () => {
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByText("Sistem sağlıklı")).toBeInTheDocument();
    expect(screen.getByText(/Sürüm/)).toBeInTheDocument();
    for (const label of ["Araçlar", "Anahtarlık", "Depolama", "D-Bus", "Zamanlayıcı"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText(/Profil/)).toBeInTheDocument();
    expect(screen.getByText("0 task")).toBeInTheDocument();
    // Saglikli raporda eksik arac uyari kutusu yoktur.
    expect(screen.queryByText(/sudo pacman/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Eksik zorunlu/)).not.toBeInTheDocument();
  });

  it("renders issues, missing tools and probe details for a failing report", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: issueReport, error: null });
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByText("Sorunlar tespit edildi")).toBeInTheDocument();
    expect(screen.getByText(/Eksik zorunlu: debtap/)).toBeInTheDocument();
    expect(screen.getByText(/Eksik opsiyonel: distrobox/)).toBeInTheDocument();
    // String probe detayi oldugu gibi, object detayi JSON olarak render edilir.
    expect(screen.getByText("secret-service unavailable")).toBeInTheDocument();
    expect(screen.getByText('{"bus":"session"}')).toBeInTheDocument();
    // tools.ok false oldugunda pacman ipucu kutusu gosterilir.
    expect(screen.getByText(/sudo pacman -S --needed debtap/)).toBeInTheDocument();
    // Profil/gorev alanlari yoksa ilgili satirlar render edilmez.
    expect(screen.queryByText(/Profil/)).not.toBeInTheDocument();
    expect(screen.queryByText(/task/)).not.toBeInTheDocument();
  });

  it("renders a minimal report without optional profile and scheduler details", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: minimalReport, error: null });
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByText("Sistem sağlıklı")).toBeInTheDocument();
    expect(screen.queryByText(/Profil/)).not.toBeInTheDocument();
    expect(screen.queryByText(/task/)).not.toBeInTheDocument();
  });

  it("falls back to String() when a probe detail is not JSON-serializable", async () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0",
      id: 1,
      result: { ...healthyReport, ok: false, dbus: { ok: false, detail: circular } },
      error: null,
    });
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByText("[object Object]")).toBeInTheDocument();
  });

  it("copies the diagnostics Markdown to the clipboard and toasts success", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: copyFixture, error: null });
    renderPanel();
    // fireEvent: userEvent.setup() navigator.clipboard stub'imizi degistirirdi.
    fireEvent.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    const copyBtn = await screen.findByRole("button", { name: /Tanıyı kopyala/ });
    await act(async () => {
      fireEvent.click(copyBtn);
    });
    await vi.waitFor(() => expect(clipboardWriteText).toHaveBeenCalledTimes(1), { timeout: 5000 });
    const md = clipboardWriteText.mock.calls[0][0] as string;
    expect(md).toContain("# PkgForge Diagnostics");
    expect(md).toContain("- version: 2.1.0");
    expect(md).toContain("- ok: false");
    expect(md).toContain("- tools.ok: false");
    expect(md).toContain("- missing_required: debtap, pacman");
    expect(md).toContain("- missing_optional: distrobox");
    expect(md).toContain("- keyring.ok: false");
    expect(md).toContain("- storage.ok: true (profile: default)");
    expect(md).toContain("- scheduler.ok: true (tasks: 3)");
    expect(md).toContain("- platform: " + navigator.platform);
    expect(md).toContain("- lang: " + navigator.language);
    expect(await screen.findByText("Tanı panoya kopyalandı")).toBeInTheDocument();
  });

  it("copies a minimal report without the optional Markdown sections", async () => {
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: minimalReport, error: null });
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    const copyBtn = await screen.findByRole("button", { name: /Tanıyı kopyala/ });
    await act(async () => {
      fireEvent.click(copyBtn);
    });
    await vi.waitFor(() => expect(clipboardWriteText).toHaveBeenCalledTimes(1), { timeout: 5000 });
    const md = clipboardWriteText.mock.calls[0][0] as string;
    expect(md).toContain("- storage.ok: true");
    expect(md).not.toContain("(profile:");
    expect(md).toContain("- scheduler.ok: true");
    expect(md).not.toContain("(tasks:");
    expect(md).not.toContain("missing_required");
    expect(md).not.toContain("missing_optional");
  });

  it("toasts an error when copying the diagnostics fails", async () => {
    clipboardWriteText.mockRejectedValue(new Error("clipboard blocked"));
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    const copyBtn = await screen.findByRole("button", { name: /Tanıyı kopyala/ });
    await act(async () => {
      fireEvent.click(copyBtn);
    });
    expect(await screen.findByText("Kopyalanamadı")).toBeInTheDocument();
  });
});

describe("DoctorPanel — polkit teşhisi (Faz 15)", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue({ jsonrpc: "2.0", id: 1, result: healthyReport, error: null });
    clipboardWriteText.mockReset();
    clipboardWriteText.mockResolvedValue(undefined);
    installClipboardStub();
  });

  it("polkit bölümü eksikse (eski yanıt) satır render edilmez", async () => {
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    await screen.findByText(/2.0.0/);
    expect(screen.queryByText(/polkit/)).not.toBeInTheDocument();
  });

  it("polkit sağlıklıysa satır yeşilende görünür, uyarı kutusu çıkmaz", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0", id: 1,
      result: { ...healthyReport, polkit: { ok: true } },
      error: null,
    });
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(await screen.findByText(/Yetki \(polkit\) kurulumu/)).toBeInTheDocument();
    expect(screen.queryByText(/install.sh/)).not.toBeInTheDocument();
  });

  it("polkit bozuksa detay + eylem önerisi (install.sh) görünür", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0", id: 1,
      result: {
        ...healthyReport,
        polkit: {
          ok: false,
          detail: "org.pkgforge.helper.policy kurulu değil — pkexec her çağrıda parola ister.",
        },
      },
      error: null,
    });
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    expect(
      await screen.findByText(/pkexec her çağrıda parola ister/),
    ).toBeInTheDocument();
    expect(screen.getByText(/sudo \.\/scripts\/install\.sh/)).toBeInTheDocument();
  });

  it("kopyalanan tanıya polkit satırı düşer", async () => {
    invokeMock.mockResolvedValue({
      jsonrpc: "2.0", id: 1,
      result: {
        ...healthyReport,
        polkit: { ok: false, detail: "policy yok" },
      },
      error: null,
    });
    // fireEvent: userEvent.setup() navigator.clipboard stub'imizi degistirirdi.
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: /Teşhis Çalıştır/ }));
    const copyBtn = await screen.findByRole("button", { name: /Tanıyı kopyala/ });
    await act(async () => {
      fireEvent.click(copyBtn);
    });
    await vi.waitFor(() => expect(clipboardWriteText).toHaveBeenCalledTimes(1), { timeout: 5000 });
    const copied = clipboardWriteText.mock.calls[0][0] as string;
    expect(copied).toContain("polkit.ok: false");
    expect(copied).toContain("policy yok");
  });
});
