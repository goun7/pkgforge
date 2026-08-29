import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

// Kok kabugun cocuk bilesenleri basit stub'larla izole edilir; boylece
// App'in kendi dallari (gezinti, klavye, gecmis, palet) test edilir.
const flags = vi.hoisted(() => ({ fleetSuspend: false }));

vi.mock("../components/ui/Toast", () => ({
  ToastProvider: ({ children }: any) => <>{children}</>,
}));
vi.mock("../components/SidecarGuard", () => ({ SidecarGuard: () => null }));
vi.mock("../components/Onboarding", () => ({ Onboarding: () => null }));
vi.mock("../components/WhatsNew", () => ({ WhatsNew: () => null }));
vi.mock("../components/FeatureTour", () => ({ FeatureTour: () => null }));
vi.mock("../components/ShortcutsDialog", () => ({ ShortcutsDialog: () => null }));
vi.mock("../components/TopbarActions", () => ({
  TopbarActions: () => <div data-testid="topbar-actions" />,
}));
vi.mock("../components/Topbar", () => ({
  Topbar: ({ title, subtitle, right }: any) => (
    <div data-testid="topbar">
      <h1>{title}</h1>
      {subtitle ? <p>{subtitle}</p> : null}
      {right}
    </div>
  ),
}));
vi.mock("../components/Sidebar", () => ({
  Sidebar: ({ active, onNavigate, recent }: any) => (
    <nav data-testid="sidebar" data-active={active}>
      {[
        "convert", "installed", "settings", "browse", "updates", "security",
        "reports", "plugins", "export", "compare", "tools", "fleet",
      ].map((p) => (
        <button key={p} data-nav={p} onClick={() => onNavigate(p)}>
          {p}
        </button>
      ))}
      {(recent ?? []).map((r: string) => (
        <span key={"recent-" + r} data-testid={"recent-" + r}>
          {r}
        </span>
      ))}
    </nav>
  ),
}));
vi.mock("../components/CommandPalette", () => ({
  CommandPalette: ({ open, onClose, commands }: any) =>
    open ? (
      <div data-testid="command-palette">
        <button data-testid="palette-close" onClick={onClose}>
          kapat
        </button>
        {commands.map((c: any) => (
          <button key={c.id} data-cmd={c.id} data-hint={c.hint ?? ""} onClick={c.action}>
            {c.label}
          </button>
        ))}
      </div>
    ) : null,
}));
vi.mock("../components/EmptyState", () => ({
  EmptyState: ({ title, description }: any) => (
    <div data-testid="empty-state" data-title={title}>
      {description}
    </div>
  ),
}));
vi.mock("../components/ErrorBoundary", () => ({
  ErrorBoundary: ({ children }: any) => <>{children}</>,
}));
vi.mock("../pages/Convert", () => ({
  Convert: () => <div data-testid="page-convert" />,
}));
vi.mock("../pages/Installed", () => ({ Installed: () => <div data-testid="page-installed" /> }));
vi.mock("../pages/Settings", () => ({ Settings: () => <div data-testid="page-settings" /> }));
vi.mock("../pages/Security", () => ({ Security: () => <div data-testid="page-security" /> }));
vi.mock("../pages/Updates", () => ({ Updates: () => <div data-testid="page-updates" /> }));
vi.mock("../pages/Reports", () => ({ Reports: () => <div data-testid="page-reports" /> }));
vi.mock("../pages/Export", () => ({ Export: () => <div data-testid="page-export" /> }));
vi.mock("../pages/Plugins", () => ({ Plugins: () => <div data-testid="page-plugins" /> }));
vi.mock("../pages/Compare", () => ({ Compare: () => <div data-testid="page-compare" /> }));
vi.mock("../pages/Browse", () => ({ Browse: () => <div data-testid="page-browse" /> }));
vi.mock("../pages/Tools", () => ({ Tools: () => <div data-testid="page-tools" /> }));
vi.mock("../pages/Fleet", () => ({
  Fleet: () => {
    // Suspense fallback (PageLoading) dalini deterministik test etmek icin.
    if (flags.fleetSuspend) throw new Promise<void>(() => {});
    return <div data-testid="page-fleet" />;
  },
}));

import App from "../App";
import { setLang } from "../lib/lang";

let historyResp: { result: unknown; error: unknown };

function cmdSel(id: string): string {
  return '[data-cmd="' + id + '"]';
}

beforeEach(() => {
  flags.fleetSuspend = false;
  historyResp = { result: [], error: null };
  invokeMock.mockReset();
  invokeMock.mockImplementation(async (_cmd: unknown, args?: { method?: string }) => {
    if (args?.method === "history.list") {
      return { jsonrpc: "2.0", id: 1, result: historyResp.result, error: historyResp.error };
    }
    if (args?.method === "settings.get") {
      return { jsonrpc: "2.0", id: 1, result: { language: "tr", theme: "dark" }, error: null };
    }
    return { jsonrpc: "2.0", id: 1, result: {}, error: null };
  });
});

afterEach(() => {
  setLang("tr");
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.documentElement.removeAttribute("data-theme");
});

async function renderApp() {
  const utils = render(<App />);
  // Mount effect'lerinin (history.list / loadLang / loadTheme) cozulmesini bekle.
  await act(async () => {});
  return utils;
}

async function clickNav(page: string) {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: page }));
  });
}

async function pressWindow(opts: { key: string; ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean }) {
  await act(async () => {
    fireEvent.keyDown(window, opts);
  });
}

function heading() {
  return screen.getByRole("heading", { level: 1 });
}

describe("App kok kabuk", () => {
  it("renders the convert shell: title, subtitle, skip link, live announcement", async () => {
    await renderApp();
    expect(heading()).toHaveTextContent("Dönüştür");
    expect(screen.getByText("Linux paketlerini Arch için dönüştürün")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "İçeriğe atla" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Dönüştür sayfası açıldı");
    expect(screen.getByTestId("topbar-actions")).toBeInTheDocument();
    expect(screen.getByTestId("page-convert").parentElement!.className).toBe("h-full");
  });

  it("restores the last active page from localStorage", async () => {
    localStorage.setItem("pkgforge.lastPage", "settings");
    await renderApp();
    expect(await screen.findByTestId("page-settings")).toBeInTheDocument();
    expect(heading()).toHaveTextContent("Ayarlar");
    expect(screen.getByTestId("page-convert").parentElement!.className).toBe("hidden");
  });

  it("falls back to convert when the saved page is unknown", async () => {
    localStorage.setItem("pkgforge.lastPage", "bogus");
    await renderApp();
    expect(heading()).toHaveTextContent("Dönüştür");
  });

  it("falls back to convert when localStorage cannot be read", async () => {
    vi.spyOn(localStorage, "getItem").mockImplementation(() => {
      throw new Error("storage broken");
    });
    await renderApp();
    expect(heading()).toHaveTextContent("Dönüştür");
  });

  it("restores recent pages from localStorage, filtering unknown ids", async () => {
    localStorage.setItem("pkgforge.recentPages", JSON.stringify(["settings", "bogus", "reports"]));
    await renderApp();
    expect(screen.getByTestId("recent-settings")).toBeInTheDocument();
    expect(screen.getByTestId("recent-reports")).toBeInTheDocument();
    expect(screen.queryByTestId("recent-bogus")).toBeNull();
  });

  it("starts with an empty recent list when stored JSON is corrupt", async () => {
    localStorage.setItem("pkgforge.recentPages", "{not-json");
    await renderApp();
    expect(screen.queryByTestId(/^recent-/)).toBeNull();
  });

  it("navigates via the sidebar, persists the page and updates recents", async () => {
    await renderApp();
    await clickNav("settings");
    expect(await screen.findByTestId("page-settings")).toBeInTheDocument();
    expect(heading()).toHaveTextContent("Ayarlar");
    expect(localStorage.getItem("pkgforge.lastPage")).toBe("settings");
    await clickNav("installed");
    expect(await screen.findByTestId("page-installed")).toBeInTheDocument();
    expect(heading()).toHaveTextContent("Kurulanlar");
    expect(screen.getByRole("status")).toHaveTextContent("Kurulanlar sayfası açıldı");
    expect(JSON.parse(localStorage.getItem("pkgforge.recentPages")!)).toEqual(["installed", "settings"]);
    expect(screen.getByTestId("recent-installed")).toBeInTheDocument();
    expect(screen.getByTestId("recent-settings")).toBeInTheDocument();
  });

  it("keeps Convert mounted but hidden while another page is active", async () => {
    await renderApp();
    await clickNav("reports");
    expect(await screen.findByTestId("page-reports")).toBeInTheDocument();
    expect(screen.getByTestId("page-convert")).toBeInTheDocument();
    expect(screen.getByTestId("page-convert").parentElement!.className).toBe("hidden");
    await clickNav("convert");
    expect(heading()).toHaveTextContent("Dönüştür");
    expect(screen.getByTestId("page-convert").parentElement!.className).toBe("h-full");
  });

  it("keeps at most three unique recent pages, newest first", async () => {
    await renderApp();
    await clickNav("settings");
    await clickNav("installed");
    await clickNav("reports");
    await clickNav("browse");
    expect(JSON.parse(localStorage.getItem("pkgforge.recentPages")!)).toEqual([
      "browse", "reports", "installed",
    ]);
    await clickNav("reports"); // tekrar gezmek one tasir, liste 3 ile sinirli kalir
    expect(JSON.parse(localStorage.getItem("pkgforge.recentPages")!)).toEqual([
      "reports", "browse", "installed",
    ]);
  });

  it("Alt+ArrowLeft/Right walks the page history stack with bounds", async () => {
    await renderApp();
    await clickNav("settings");
    await clickNav("installed");
    await pressWindow({ key: "ArrowLeft", altKey: true });
    expect(heading()).toHaveTextContent("Ayarlar");
    await pressWindow({ key: "ArrowLeft", altKey: true });
    expect(heading()).toHaveTextContent("Dönüştür");
    await pressWindow({ key: "ArrowLeft", altKey: true }); // yigit basi: degismez
    expect(heading()).toHaveTextContent("Dönüştür");
    await pressWindow({ key: "ArrowRight", altKey: true });
    expect(heading()).toHaveTextContent("Ayarlar");
    await pressWindow({ key: "ArrowRight", altKey: true });
    expect(heading()).toHaveTextContent("Kurulanlar");
    await pressWindow({ key: "ArrowRight", altKey: true }); // yigit sonu: degismez
    expect(heading()).toHaveTextContent("Kurulanlar");
  });

  it("navigating after goBack discards the forward stack", async () => {
    await renderApp();
    await clickNav("settings");
    await clickNav("installed");
    await pressWindow({ key: "ArrowLeft", altKey: true });
    expect(heading()).toHaveTextContent("Ayarlar");
    await clickNav("browse");
    expect(await screen.findByTestId("page-browse")).toBeInTheDocument();
    await pressWindow({ key: "ArrowRight", altKey: true }); // ileri yigit budandi
    expect(heading()).toHaveTextContent("AUR Gözat");
  });

  it("does not push the same page twice onto the history stack", async () => {
    await renderApp();
    await clickNav("settings");
    await clickNav("settings");
    await pressWindow({ key: "ArrowLeft", altKey: true });
    expect(heading()).toHaveTextContent("Dönüştür");
  });

  it("Alt+1..9 jumps to the corresponding page; Alt+0 is ignored", async () => {
    await renderApp();
    await pressWindow({ key: "2", altKey: true });
    expect(await screen.findByTestId("page-installed")).toBeInTheDocument();
    expect(heading()).toHaveTextContent("Kurulanlar");
    await pressWindow({ key: "3", altKey: true });
    expect(heading()).toHaveTextContent("Ayarlar");
    await pressWindow({ key: "9", altKey: true });
    expect(heading()).toHaveTextContent("Dışa Aktar");
    await pressWindow({ key: "0", altKey: true });
    expect(heading()).toHaveTextContent("Dışa Aktar");
  });

  it("Alt+digit shortcuts are ignored while typing in form fields", async () => {
    await renderApp();
    const input = document.createElement("input");
    const textarea = document.createElement("textarea");
    const select = document.createElement("select");
    const editable = document.createElement("div");
    editable.contentEditable = "true";
    // jsdom isContentEditable'i hesaplamaz; dali yine de ortmek icin elle ayarla.
    Object.defineProperty(editable, "isContentEditable", { value: true });
    document.body.append(input, textarea, select, editable);
    try {
      await act(async () => { fireEvent.keyDown(input, { key: "2", altKey: true }); });
      expect(heading()).toHaveTextContent("Dönüştür");
      await act(async () => { fireEvent.keyDown(textarea, { key: "3", altKey: true }); });
      expect(heading()).toHaveTextContent("Dönüştür");
      await act(async () => { fireEvent.keyDown(select, { key: "4", altKey: true }); });
      expect(heading()).toHaveTextContent("Dönüştür");
      await act(async () => { fireEvent.keyDown(editable, { key: "5", altKey: true }); });
      expect(heading()).toHaveTextContent("Dönüştür");
    } finally {
      input.remove();
      textarea.remove();
      select.remove();
      editable.remove();
    }
  });

  it("Ctrl+K toggles the command palette; close button hides it", async () => {
    await renderApp();
    expect(screen.queryByTestId("command-palette")).toBeNull();
    await pressWindow({ key: "k", ctrlKey: true });
    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(screen.getByTestId("palette-close"));
    });
    expect(screen.queryByTestId("command-palette")).toBeNull();
    await pressWindow({ key: "k", ctrlKey: true });
    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    await pressWindow({ key: "K", metaKey: true }); // Cmd+K da ayni dali kullanir
    expect(screen.queryByTestId("command-palette")).toBeNull();
  });

  it("Ctrl+/ dispatches the shortcuts dialog event", async () => {
    await renderApp();
    const spy = vi.fn();
    window.addEventListener("pkgforge:open-shortcuts", spy);
    try {
      await pressWindow({ key: "/", ctrlKey: true });
      expect(spy).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener("pkgforge:open-shortcuts", spy);
    }
  });

  it("palette nav commands carry Alt hints only for the first nine pages", async () => {
    await renderApp();
    await pressWindow({ key: "k", ctrlKey: true });
    const palette = screen.getByTestId("command-palette");
    const hint = (id: string) =>
      palette.querySelector('[data-cmd="nav-' + id + '"]')!.getAttribute("data-hint");
    expect(hint("convert")).toBe("Alt+1");
    expect(hint("export")).toBe("Alt+9");
    expect(hint("compare")).toBe("");
    expect(hint("fleet")).toBe("");
  });

  it("builds package commands from history without duplicates or empty names", async () => {
    historyResp.result = [
      { package_name: "vim" },
      { package_name: "vim" },
      { package_name: "" },
      { package_name: null },
      { package_name: "git" },
    ];
    await renderApp();
    await pressWindow({ key: "k", ctrlKey: true });
    const palette = screen.getByTestId("command-palette");
    await waitFor(() => expect(palette.querySelector(cmdSel("pkg-vim"))).not.toBeNull());
    expect(palette.querySelectorAll(cmdSel("pkg-vim"))).toHaveLength(1);
    expect(palette.querySelector(cmdSel("pkg-git"))).not.toBeNull();
    expect(palette.querySelectorAll('[data-cmd^="pkg-"]')).toHaveLength(2);
  });

  it("caps the package command list at 20 entries", async () => {
    historyResp.result = Array.from({ length: 25 }, (_, i) => ({ package_name: "pkg-" + i }));
    await renderApp();
    await pressWindow({ key: "k", ctrlKey: true });
    const palette = screen.getByTestId("command-palette");
    expect(palette.querySelectorAll('[data-cmd^="pkg-"]')).toHaveLength(20);
  });

  it("ignores a non-array history.list result", async () => {
    historyResp.result = { unexpected: true };
    await renderApp();
    expect(heading()).toHaveTextContent("Dönüştür");
    await pressWindow({ key: "k", ctrlKey: true });
    expect(screen.getByTestId("command-palette").querySelectorAll('[data-cmd^="pkg-"]')).toHaveLength(0);
  });

  it("survives a failing history.list call", async () => {
    historyResp = { result: null, error: { code: -1, message: "sidecar down" } };
    await renderApp();
    expect(heading()).toHaveTextContent("Dönüştür");
    await pressWindow({ key: "k", ctrlKey: true });
    expect(screen.getByTestId("command-palette").querySelectorAll('[data-cmd^="pkg-"]')).toHaveLength(0);
  });

  it("selecting a package command filters Installed and navigates there", async () => {
    historyResp.result = [{ package_name: "vim" }];
    await renderApp();
    const spy = vi.fn();
    window.addEventListener("pkgforge:installed-filter", spy as EventListener);
    try {
      await pressWindow({ key: "k", ctrlKey: true });
      const palette = screen.getByTestId("command-palette");
      await waitFor(() => expect(palette.querySelector(cmdSel("pkg-vim"))).not.toBeNull());
      await act(async () => {
        fireEvent.click(palette.querySelector(cmdSel("pkg-vim"))!);
      });
      expect(sessionStorage.getItem("pkgforge.installed.filter")).toBe("vim");
      expect(spy).toHaveBeenCalledTimes(1);
      expect((spy.mock.calls[0][0] as CustomEvent).detail).toBe("vim");
      expect(await screen.findByTestId("page-installed")).toBeInTheDocument();
      expect(heading()).toHaveTextContent("Kurulanlar");
    } finally {
      window.removeEventListener("pkgforge:installed-filter", spy as EventListener);
    }
  });

  it("theme commands apply the theme and persist it via settings.set", async () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    );
    await renderApp();
    await pressWindow({ key: "k", ctrlKey: true });
    const palette = screen.getByTestId("command-palette");
    const clickCmd = async (id: string) => {
      await act(async () => {
        fireEvent.click(palette.querySelector(cmdSel(id))!);
      });
    };
    await clickCmd("action-theme-light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    await clickCmd("action-theme-system"); // OS koyu tercih: dark'a cozulur
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    await clickCmd("action-theme-oled");
    expect(document.documentElement.getAttribute("data-theme")).toBe("oled");
    const setCalls = invokeMock.mock.calls.filter(
      (c) => (c[1] as { method?: string })?.method === "settings.set",
    );
    expect(setCalls.map((c) => (c[1] as { params: unknown }).params)).toEqual([
      { theme: "light" },
      { theme: "system" },
      { theme: "oled" },
    ]);
  });

  it("language commands switch the whole shell language", async () => {
    await renderApp();
    await clickNav("settings");
    expect(heading()).toHaveTextContent("Ayarlar");
    await pressWindow({ key: "k", ctrlKey: true });
    const clickCmd = async (id: string) => {
      await act(async () => {
        fireEvent.click(screen.getByTestId("command-palette").querySelector(cmdSel(id))!);
      });
    };
    await clickCmd("action-lang-en");
    await waitFor(() => expect(heading()).toHaveTextContent("Settings"));
    await clickCmd("action-lang-en"); // ayni dil tekrar secilince degisim yok
    expect(heading()).toHaveTextContent("Settings");
    await clickCmd("action-lang-tr");
    await waitFor(() => expect(heading()).toHaveTextContent("Ayarlar"));
  });

  it("onboarding, tour and shortcut commands dispatch their events", async () => {
    localStorage.setItem("pkgforge.onboarding.seen", "1");
    await renderApp();
    const reopen = vi.fn();
    const tour = vi.fn();
    const shortcuts = vi.fn();
    window.addEventListener("pkgforge:reopen-onboarding", reopen);
    window.addEventListener("pkgforge:open-tour", tour);
    window.addEventListener("pkgforge:open-shortcuts", shortcuts);
    try {
      await pressWindow({ key: "k", ctrlKey: true });
      const palette = screen.getByTestId("command-palette");
      for (const id of ["action-onboarding", "action-tour", "action-shortcuts"]) {
        await act(async () => {
          fireEvent.click(palette.querySelector(cmdSel(id))!);
        });
      }
      expect(localStorage.getItem("pkgforge.onboarding.seen")).toBeNull();
      expect(reopen).toHaveBeenCalledTimes(1);
      expect(tour).toHaveBeenCalledTimes(1);
      expect(shortcuts).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener("pkgforge:reopen-onboarding", reopen);
      window.removeEventListener("pkgforge:open-tour", tour);
      window.removeEventListener("pkgforge:open-shortcuts", shortcuts);
    }
  });

  it("shows the Suspense fallback while a lazy page is loading", async () => {
    flags.fleetSuspend = true;
    await renderApp();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "fleet" }));
    });
    await waitFor(() => expect(document.querySelector(".animate-spin")).not.toBeNull());
    expect(screen.queryByTestId("page-fleet")).toBeNull();
  });

  it("tolerates localStorage write failures during navigation", async () => {
    await renderApp();
    vi.spyOn(localStorage, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded");
    });
    await clickNav("settings");
    expect(await screen.findByTestId("page-settings")).toBeInTheDocument();
    expect(heading()).toHaveTextContent("Ayarlar");
  });
});
