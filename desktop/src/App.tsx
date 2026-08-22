import { useState } from "react";
import { Sidebar, type PageId } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { ToastProvider } from "./components/ui/Toast";
import { Convert } from "./pages/Convert";
import { Installed } from "./pages/Installed";
import { Settings } from "./pages/Settings";
import { EmptyState } from "./components/EmptyState";
import { Construction } from "lucide-react";

const PAGE_TITLES: Record<PageId, string> = {
  convert: "Dönüştür",
  installed: "Kurulanlar",
  settings: "Ayarlar",
  browse: "AUR Gözat",
  updates: "Güncellemeler",
  security: "Güvenlik",
  reports: "Raporlar",
  plugins: "Eklentiler",
};

const READY_PAGES: PageId[] = ["convert", "installed", "settings"];

export default function App() {
  const [page, setPage] = useState<PageId>("convert");

  return (
    <ToastProvider>
      <div className="flex h-screen overflow-hidden bg-[var(--bg-base)]">
        <Sidebar active={page} onNavigate={setPage} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar title={PAGE_TITLES[page]} />
          <main className="min-h-0 flex-1 overflow-hidden">
            {page === "convert" && <Convert />}
            {page === "installed" && <Installed />}
            {page === "settings" && <Settings />}
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
