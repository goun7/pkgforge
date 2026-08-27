import {
  ArrowLeftRight,
  PackageCheck,
  Settings,
  Globe,
  RefreshCw,
  ShieldCheck,
  FileText,
  Puzzle,
  PackageOpen,
  GitCompare,
  Wrench,
  Server,
} from "lucide-react";
import { cn } from "../lib/utils";

export type PageId =
  | "convert"
  | "installed"
  | "settings"
  | "browse"
  | "updates"
  | "security"
  | "reports"
  | "plugins"
  | "export"
  | "compare"
  | "tools"
  | "fleet";

export interface SidebarProps {
  active: PageId;
  onNavigate: (page: PageId) => void;
}

const NAV_ITEMS: { id: PageId; label: string; icon: typeof ArrowLeftRight; soon?: boolean }[] = [
  { id: "convert", label: "Dönüştür", icon: ArrowLeftRight },
  { id: "installed", label: "Kurulanlar", icon: PackageCheck },
  { id: "browse", label: "AUR Gözat", icon: Globe },
  { id: "updates", label: "Güncellemeler", icon: RefreshCw },
  { id: "security", label: "Güvenlik", icon: ShieldCheck },
  { id: "reports", label: "Raporlar", icon: FileText },
  { id: "export", label: "Dışa Aktar", icon: PackageOpen },
  { id: "compare", label: "Karşılaştır", icon: GitCompare },
  { id: "plugins", label: "Eklentiler", icon: Puzzle },
  { id: "tools", label: "Araclar", icon: Wrench },
  { id: "fleet", label: "Fleet", icon: Server },
  { id: "settings", label: "Ayarlar", icon: Settings },
];

export function Sidebar({ active, onNavigate }: SidebarProps) {
  return (
    <nav
      aria-label="Ana gezinme"
      className="flex w-56 shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3"
    >
      <div className="mb-4 flex items-center gap-2 px-2 pt-1">
        <img src="/favicon.svg" alt="PkgForge" className="h-7 w-7" />
        <span className="bg-[var(--brand-gradient)] bg-clip-text text-lg font-bold text-transparent">
          PkgForge
        </span>
      </div>
      <ul className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ id, label, icon: Icon, soon }) => (
          <li key={id}>
            <button
              onClick={() => onNavigate(id)}
              aria-current={active === id ? "page" : undefined}
              className={cn(
                "flex w-full items-center gap-3 rounded-[var(--radius-btn)] px-3 py-2 text-sm font-medium transition-colors",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand-blue)]",
                active === id
                  ? "bg-[var(--brand-blue)]/12 text-[var(--brand-blue)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]",
              )}
            >
              <Icon size={17} />
              <span className="flex-1 text-left">{label}</span>
              {soon && (
                <span className="rounded-full bg-[var(--bg-elevated)] px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-[var(--text-muted)]">
                  Faz 1-2
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
