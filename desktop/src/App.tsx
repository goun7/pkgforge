import { useEffect, useState } from "react";
import { Sidebar, type PageId } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { ToastProvider } from "./components/ui/Toast";
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
import { loadLang } from "./lib/lang";

const PAGE_TITLES: Record<PageId, string> = {
  convert: "Dönüştür",
  installed: "Kurulanlar",
  settings: "Ayarlar",
  browse: "AUR Gözat",
  updates: "Güncellemeler",
  security: "Güvenlik",
  reports: "Raporlar",
  plugins: "Eklentiler",
  export: "Dışa Aktar",
  compare: "Karşılaştır",
  tools: "Araçlar",
  fleet: "Fleet",
};

const READY_PAGES: PageId[] = ["convert", "installed", "settings", "security", "updates", "reports", "export", "plugins", "compare", "browse", "tools", "fleet"];

export default function App() {
  const [page, setPage] = useState<PageId>("convert");

  // F5.20: hydrate the shared live-language store once at startup.
  useEffect(() => {
    void loadLang();
  }, []);

  return (
    <ToastProvider>
      <div className="flex h-screen overflow-hidden bg-[var(--bg-base)]">
        <Sidebar active={page} onNavigate={setPage} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar title={PAGE_TITLES[page]} />
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
    </ToastProvider>
  );
}
