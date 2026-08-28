import { useEffect, useMemo, useState } from "react";
import { Sidebar, type PageId } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { TopbarActions } from "./components/TopbarActions";
import { ToastProvider } from "./components/ui/Toast";
import { CommandPalette, type Command } from "./components/CommandPalette";
import { Onboarding } from "./components/Onboarding";
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
import { Construction } from "lucide-react";
import { loadLang, useLang, getLang, setLang } from "./lib/lang";
import { loadTheme, applyTheme, resolveTheme } from "./lib/theme";
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

const READY_PAGES: PageId[] = ["convert", "installed", "settings", "security", "updates", "reports", "export", "plugins", "compare", "browse", "tools", "fleet"];

export default function App() {
  const [page, setPage] = useState<PageId>("convert");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const lang = useLang();
  const t = tFor(lang);

  // F5.20: hydrate the shared live-language store once at startup.
  useEffect(() => {
    void loadLang();
    void loadTheme();
  }, []);

  // Komut paleti komutlari: sayfa gecisleri + tema/dil eylemleri.
  const commands = useMemo<Command[]>(() => {
    const nav: Command[] = (Object.keys(PAGE_TITLES) as PageId[]).map((id, i) => ({
      id: `nav-${id}`,
      label: t(PAGE_TITLES[id]),
      hint: i < 9 ? `Alt+${i + 1}` : undefined,
      action: () => setPage(id),
    }));
    return [
      ...nav,
      {
        id: "action-theme",
        label: lang === "tr" ? "Temayı değiştir (Koyu/Açık)" : "Toggle theme (Dark/Light)",
        action: () => {
          const cur = resolveTheme(document.documentElement.getAttribute("data-theme") ?? "dark");
          const next = cur === "dark" ? "light" : "dark";
          applyTheme(next);
          void call("settings.set", { theme: next }).catch(() => {});
        },
      },
      {
        id: "action-lang",
        label: lang === "tr" ? "Dili değiştir (Türkçe/English)" : "Switch language (Turkish/English)",
        action: () => {
          const next = getLang() === "tr" ? "en" : "tr";
          setLang(next);
          void call("settings.set", { language: next }).catch(() => {});
        },
      },
    ];
  }, [t, lang]);

  // Global klavye kisayollari: Ctrl/Cmd+K komut paleti, Alt+1..9 sayfa gecisi.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
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
      <div className="flex h-screen overflow-hidden bg-[var(--bg-base)]">
        <Sidebar active={page} onNavigate={setPage} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar title={t(PAGE_TITLES[page])} right={<TopbarActions />} />
          <main className="min-h-0 flex-1 overflow-hidden">
            {/* Convert her zaman mount kalir: sekme degisince donusum state'i
                ve event listener'lar kaybolmasin (aktif degilse sadece gizlenir). */}
            <div className={page === "convert" ? "h-full" : "hidden"}>
              <Convert />
            </div>
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
                title={`${PAGE_TITLES[page]} yakında`}
                description="Bu bölüm Faz 1-2 genişleme planında. Şimdilik Dönüştür sekmesini kullanabilirsiniz."
              />
            )}
          </main>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={commands} />
      <Onboarding />
    </ToastProvider>
  );
}
