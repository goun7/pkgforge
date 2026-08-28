import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
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
// Faz 10 (4.1): sayfalar tembel yuklenir (kod bolme). Convert her zaman mount
// kaldigi icin statik import olarak kalir; diger 11 sayfa lazy.
const Installed = lazy(() => import("./pages/Installed").then((m) => ({ default: m.Installed })));
const Settings = lazy(() => import("./pages/Settings").then((m) => ({ default: m.Settings })));
const Security = lazy(() => import("./pages/Security").then((m) => ({ default: m.Security })));
const Updates = lazy(() => import("./pages/Updates").then((m) => ({ default: m.Updates })));
const Reports = lazy(() => import("./pages/Reports").then((m) => ({ default: m.Reports })));
const Export = lazy(() => import("./pages/Export").then((m) => ({ default: m.Export })));
const Plugins = lazy(() => import("./pages/Plugins").then((m) => ({ default: m.Plugins })));
const Compare = lazy(() => import("./pages/Compare").then((m) => ({ default: m.Compare })));
const Browse = lazy(() => import("./pages/Browse").then((m) => ({ default: m.Browse })));
const Tools = lazy(() => import("./pages/Tools").then((m) => ({ default: m.Tools })));
const Fleet = lazy(() => import("./pages/Fleet").then((m) => ({ default: m.Fleet })));
import { EmptyState } from "./components/EmptyState";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Construction, Loader2 } from "lucide-react";
import { loadLang, useLang, setLang } from "./lib/lang";
import { loadTheme, applyTheme, loadAccentLocal } from "./lib/theme";
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

// Faz 10 (4.1): tembel yuklenen sayfa yuklenene kadar gosterilen durum.
function PageLoading() {
  return (
    <div className="flex h-full items-center justify-center">
      <Loader2 className="animate-spin text-[var(--text-muted)]" size={28} aria-hidden />
    </div>
  );
}

function loadInitialPage(): PageId {
  try {
    const saved = localStorage.getItem("pkgforge.lastPage");
    if (saved && (Object.keys(PAGE_TITLES) as string[]).includes(saved)) return saved as PageId;
  } catch {
    /* depolama yok */
  }
  return "convert";
}

function loadRecentPages(): PageId[] {
  try {
    const raw = localStorage.getItem("pkgforge.recentPages");
    if (raw) {
      const arr = JSON.parse(raw) as string[];
      return arr.filter((p): p is PageId => (Object.keys(PAGE_TITLES) as string[]).includes(p));
    }
  } catch {
    /* depolama yok */
  }
  return [];
}

export default function App() {
  // Faz 8 (3.2): son aktif sayfayi localStorage'dan geri yukle.
  const [page, setPageRaw] = useState<PageId>(loadInitialPage);
  // Faz 10 (5.8): sayfa gecmisi yigini (Alt+Sol/Sag ileri-geri).
  const stackRef = useRef<PageId[]>([loadInitialPage()]);
  const idxRef = useRef(0);
  const skipPushRef = useRef(false);
  // Faz 10 (5.6): son gezilen sayfalar (sidebar'da gosterilir).
  const [recent, setRecent] = useState<PageId[]>(loadRecentPages);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const lang = useLang();
  const t = tFor(lang);
  // Faz 10 (5.9): paletten kurulu pakete atlamak icin gecmis paket adlari.
  const [pkgNames, setPkgNames] = useState<string[]>([]);

  const setPage = (p: PageId) => {
    if (!skipPushRef.current) {
      stackRef.current = stackRef.current.slice(0, idxRef.current + 1);
      if (stackRef.current[stackRef.current.length - 1] !== p) {
        stackRef.current.push(p);
        idxRef.current = stackRef.current.length - 1;
      }
    }
    skipPushRef.current = false;
    setPageRaw(p);
    setRecent((prev) => {
      const next = [p, ...prev.filter((x) => x !== p)].slice(0, 3);
      try {
        localStorage.setItem("pkgforge.recentPages", JSON.stringify(next));
      } catch {
        /* depolama yok */
      }
      return next;
    });
  };

  const goBack = () => {
    if (idxRef.current > 0) {
      idxRef.current -= 1;
      skipPushRef.current = true;
      setPage(stackRef.current[idxRef.current]);
    }
  };
  const goForward = () => {
    if (idxRef.current < stackRef.current.length - 1) {
      idxRef.current += 1;
      skipPushRef.current = true;
      setPage(stackRef.current[idxRef.current]);
    }
  };

  // Faz 10 (5.9): gecmisteki paket adlarini palet icin getir.
  useEffect(() => {
    let alive = true;
    call<{ package_name: string }[]>("history.list", { limit: 200 })
      .then((list) => {
        if (!alive || !Array.isArray(list)) return;
        const seen = new Set<string>();
        const names: string[] = [];
        for (const r of list) {
          if (r.package_name && !seen.has(r.package_name)) {
            seen.add(r.package_name);
            names.push(r.package_name);
          }
          if (names.length >= 20) break;
        }
        setPkgNames(names);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // F5.20: hydrate the shared live-language store once at startup.
  useEffect(() => {
    void loadLang();
    void loadTheme();
    loadAccentLocal(); // Faz 10 (5.1): vurgu rengi (senkron, sidecar gerektirmez)
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
    // Faz 10 (5.9): kurulu paket adlari — secilince Installed o filtreyle acilir.
    const pkgCmds: Command[] = pkgNames.map((name) => ({
      id: "pkg-" + name,
      label: name,
      hint: t("navInstalled"),
      action: () => {
        try {
          sessionStorage.setItem("pkgforge.installed.filter", name);
        } catch {
          /* depolama yok */
        }
        window.dispatchEvent(new CustomEvent("pkgforge:installed-filter", { detail: name }));
        setPage("installed");
      },
    }));
    return [...nav, ...actions, ...pkgCmds];
  }, [t, pkgNames]);

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
      // Faz 10 (5.8): sayfa gecmisinde Alt+Sol/Sag ile ileri/geri.
      if (e.altKey && e.key === "ArrowLeft") {
        e.preventDefault();
        goBack();
        return;
      }
      if (e.altKey && e.key === "ArrowRight") {
        e.preventDefault();
        goForward();
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
        <Sidebar active={page} onNavigate={setPage} recent={recent} />
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
              <Suspense fallback={<PageLoading />}>
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
              </Suspense>
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
