import { useEffect, useMemo, useState } from "react";
import { Sidebar, type PageId } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { TopbarActions } from "./components/TopbarActions";
import { ToastProvider } from "./components/ui/Toast";
import { CommandPalette, type Command } from "./components/CommandPalette";
import { Onboarding } from "./components/Onboarding";
import { WhatsNew } from "./components/WhatsNew";
import { SidecarGuard } from "./components/SidecarGuard";
import { FeatureTour } from "./components/FeatureTour";
import { ShortcutsDialog } from "./components/ShortcutsDialog";
import { Convert } from "./pages/Convert";
import { Installed } from "./pages/Installed";
import { Settings } from "./pages/Settings";
import { Security } from "./pages/Security";
import { Updates } from "./pages/Updates";
import { Reports } from "./pages/Reports";
import { Export } from "./pages/Export";
import { Plugins } from "./pages/Plugins";
import { Compare } from "./pages/Compare";
import { Browse } from "./pages/Browse";
import { Tools } from "./pages/Tools";
import { Fleet } from "./pages/Fleet";
import { EmptyState } from "./components/EmptyState";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Construction } from "lucide-react";
import { loadLang, useLang, setLang } from "./lib/lang";
import { loadTheme, applyTheme } from "./lib/theme";
import { call } from "./lib/rpc";
import { tFor, type I18nKey } from "./lib/i18n";

const PAGE_TITLES: Record<PageId, I18nKey> = {
  convert: "navConvert",
  installed: "navInstalled",
  settings: "navSettings",
  browse: "navBrowse",
  updates: "navUpdates",
  security: "navSecurity",
  reports: "navReports",
  plugins: "navPlugins",
  export: "navExport",
  compare: "navCompare",
  tools: "navTools",
  fleet: "navFleet",
};

// Faz 8 (3.3): sayfa basliklarinin altindaki kisa aciklamalar.
const PAGE_DESC: Record<PageId, I18nKey> = {
  convert: "descConvert",
  installed: "descInstalled",
  settings: "descSettings",
  browse: "descBrowse",
  updates: "descUpdates",
  security: "descSecurity",
  reports: "descReports",
  plugins: "descPlugins",
  export: "descExport",
  compare: "descCompare",
  tools: "descTools",
  fleet: "descFleet",
};

const READY_PAGES: PageId[] = ["convert", "installed", "settings", "security", "updates", "reports", "export", "plugins", "compare", "browse", "tools", "fleet"];

export default function App() {
  // Faz 8 (3.2): son aktif sayfayi localStorage'dan geri yukle.
  const [page, setPage] = useState<PageId>(() => {
    try {
      const saved = localStorage.getItem("pkgforge.lastPage");
      if (saved && (Object.keys(PAGE_TITLES) as string[]).includes(saved)) {
        return saved as PageId;
      }
    } catch {
      /* depolama yok */
    }
    return "convert";
  });
  const [paletteOpen, setPaletteOpen] = useState(false);
  const lang = useLang();
  const t = tFor(lang);

  // F5.20: hydrate the shared live-language store once at startup.
  useEffect(() => {
    void loadLang();
    void loadTheme();
  }, []);

  // Faz 8 (3.2): aktif sayfayi kalici yap.
  useEffect(() => {
    try {
      localStorage.setItem("pkgforge.lastPage", page);
    } catch {
      /* depolama yok */
    }
  }, [page]);

  // Komut paleti komutlari: sayfa gecisleri + tema/dil eylemleri.
  const commands = useMemo<Command[]>(() => {
    const nav: Command[] = (Object.keys(PAGE_TITLES) as PageId[]).map((id, i) => ({
      id: `nav-${id}`,
      label: t(PAGE_TITLES[id]),
      hint: i < 9 ? `Alt+${i + 1}` : undefined,
      action: () => setPage(id),
    }));
    // Faz 8 (2.4): daha zengin eylem komutlari (tema/dil/tanitim).
    const setThemeCmd = (theme: string) => () => {
      applyTheme(theme);
      void call("settings.set", { theme }).catch(() => {});
    };
    const setLangCmd = (language: "tr" | "en") => () => {
      setLang(language);
      void call("settings.set", { language }).catch(() => {});
    };
    const actions: Command[] = [
      { id: "action-theme-dark", label: t("cmdThemeDark"), action: setThemeCmd("dark") },
      { id: "action-theme-light", label: t("cmdThemeLight"), action: setThemeCmd("light") },
      { id: "action-theme-system", label: t("cmdThemeSystem"), action: setThemeCmd("system") },
      { id: "action-theme-oled", label: t("cmdThemeOled"), action: setThemeCmd("oled") },
      { id: "action-lang-tr", label: t("cmdLangTr"), action: setLangCmd("tr") },
      { id: "action-lang-en", label: t("cmdLangEn"), action: setLangCmd("en") },
      {
        id: "action-onboarding",
        label: t("cmdReopenOnboarding"),
        action: () => {
          try {
            localStorage.removeItem("pkgforge.onboarding.seen");
          } catch {
            /* depolama yok */
          }
          window.dispatchEvent(new Event("pkgforge:reopen-onboarding"));
        },
      },
      {
        id: "action-tour",
        label: t("cmdOpenTour"),
        action: () => {
          window.dispatchEvent(new Event("pkgforge:open-tour"));
        },
      },
      {
        id: "action-shortcuts",
        label: t("cmdShortcuts"),
        action: () => {
          window.dispatchEvent(new Event("pkgforge:open-shortcuts"));
        },
      },
    ];
    return [...nav, ...actions];
  }, [t]);

  // Global klavye kisayollari: Ctrl/Cmd+K komut paleti, Alt+1..9 sayfa gecisi.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
        return;
      }
      // Faz 9 (5.1): Ctrl+/ klavye kisayol yardimi.
      if ((e.ctrlKey || e.metaKey) && e.key === "/") {
        e.preventDefault();
        window.dispatchEvent(new Event("pkgforge:open-shortcuts"));
        return;
      }
      const target = e.target as HTMLElement | null;
      const inField =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);
      if (e.altKey && !inField) {
        const n = parseInt(e.key, 10);
        if (n >= 1 && n <= 9) {
          const ids = Object.keys(PAGE_TITLES) as PageId[];
          if (ids[n - 1]) {
            e.preventDefault();
            setPage(ids[n - 1]);
          }
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <ToastProvider>
      {/* Faz 8 (8.3): sidecar baglanti durumu bekçisi. */}
      <SidecarGuard />
      <div className="flex h-screen overflow-hidden bg-[var(--bg-base)]">
        {/* Faz 8 (5.1): klavye ile icerige atlama baglantisi. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-[var(--brand-blue)] focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
        >
          {t("skipToContent")}
        </a>
        <Sidebar active={page} onNavigate={setPage} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar title={t(PAGE_TITLES[page])} subtitle={t(PAGE_DESC[page])} right={<TopbarActions />} />
          <main id="main-content" className="min-h-0 flex-1 overflow-hidden">
            {/* Convert her zaman mount kalir: sekme degisince donusum state'i
                ve event listener'lar kaybolmasin (aktif degilse sadece gizlenir). */}
            <div className={page === "convert" ? "h-full" : "hidden"}>
              <Convert />
            </div>
            {/* Faz 8 (4.3/8.1): sayfa gecisi + sayfa duzeyli hata siniri. */}
            <ErrorBoundary variant="page" key={page}>
            <div className="page-in h-full">
              {page === "installed" && <Installed />}
              {page === "settings" && <Settings />}
              {page === "security" && <Security />}
              {page === "updates" && <Updates />}
              {page === "reports" && <Reports />}
              {page === "export" && <Export />}
              {page === "plugins" && <Plugins />}
              {page === "compare" && <Compare />}
              {page === "browse" && <Browse />}
              {page === "tools" && <Tools />}
              {page === "fleet" && <Fleet />}
              {!READY_PAGES.includes(page) && (
                <EmptyState
                  icon={Construction}
                  title={t(PAGE_TITLES[page])}
                  description={t("descConvert")}
                />
              )}
            </div>
            </ErrorBoundary>
          </main>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={commands} />
      <Onboarding />
      <WhatsNew />
      <FeatureTour />
      <ShortcutsDialog />
      {/* Faz 8 (5.2): sayfa degisimini ekran okuyucuya duyur. */}
      <div aria-live="polite" role="status" className="sr-only">
        {`${t(PAGE_TITLES[page])} ${t("pageOpened")}`}
      </div>
    </ToastProvider>
  );
}
