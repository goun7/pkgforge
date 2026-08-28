import { useState } from "react";
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
  ChevronDown,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { cn } from "../lib/utils";
import { useLang } from "../lib/lang";
import { tFor, type I18nKey } from "../lib/i18n";

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
  /** Faz 10 (5.6): son gezilen sayfalar (en yeni basta). */
  recent?: PageId[];
}

interface NavItem {
  id: PageId;
  labelKey: I18nKey;
  icon: typeof ArrowLeftRight;
}

const NAV_SECTIONS: { id: string; titleKey: I18nKey | null; items: NavItem[] }[] = [
  {
    id: "core",
    titleKey: null,
    items: [{ id: "convert", labelKey: "navConvert", icon: ArrowLeftRight }],
  },
  {
    id: "library",
    titleKey: "sectionLibrary",
    items: [
      { id: "installed", labelKey: "navInstalled", icon: PackageCheck },
      { id: "reports", labelKey: "navReports", icon: FileText },
    ],
  },
  {
    id: "discover",
    titleKey: "sectionDiscover",
    items: [
      { id: "browse", labelKey: "navBrowse", icon: Globe },
      { id: "updates", labelKey: "navUpdates", icon: RefreshCw },
    ],
  },
  {
    id: "quality",
    titleKey: "sectionQuality",
    items: [
      { id: "security", labelKey: "navSecurity", icon: ShieldCheck },
      { id: "compare", labelKey: "navCompare", icon: GitCompare },
    ],
  },
  {
    id: "system",
    titleKey: "sectionSystem",
    items: [
      { id: "export", labelKey: "navExport", icon: PackageOpen },
      { id: "tools", labelKey: "navTools", icon: Wrench },
      { id: "plugins", labelKey: "navPlugins", icon: Puzzle },
      { id: "fleet", labelKey: "navFleet", icon: Server },
      { id: "settings", labelKey: "navSettings", icon: Settings },
    ],
  },
];

const ALL_NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);

export function Sidebar({ active, onNavigate, recent }: SidebarProps) {
  const lang = useLang();
  const t = tFor(lang);
  // Faz 10 (5.6): aktif sayfa haricindeki son sayfalar.
  const recentItems = (recent ?? [])
    .filter((id) => id !== active)
    .map((id) => ALL_NAV_ITEMS.find((i) => i.id === id))
    .filter((x): x is NavItem => !!x)
    .slice(0, 3);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  // Faz 8 (3.1): kompakt modu localStorage'da sakla.
  const [compact, setCompact] = useState(() => {
    try {
      return localStorage.getItem("pkgforge.sidebar.compact") === "1";
    } catch {
      return false;
    }
  });
  const toggleCompact = () =>
    setCompact((c) => {
      const next = !c;
      try {
        localStorage.setItem("pkgforge.sidebar.compact", next ? "1" : "0");
      } catch {
        /* depolama yok */
      }
      return next;
    });
  const toggle = (id: string) =>
    setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }));

  return (
    <nav
      aria-label={t("sidebarNavAria")}
      className={cn(
        "flex shrink-0 flex-col overflow-y-auto border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3 transition-[width] duration-200",
        compact ? "w-16" : "w-56",
      )}
    >
      <div className={cn("mb-4 flex items-center gap-2 px-2 pt-1", compact && "justify-center px-0")}>
        <img src="/favicon.svg" alt="PkgForge" className="h-7 w-7 shrink-0" />
        {!compact && (
          <span className="bg-[var(--brand-gradient)] bg-clip-text text-lg font-bold text-transparent">
            PkgForge
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2">
        {/* Faz 10 (5.6): son gezilen sayfalar. */}
        {!compact && recentItems.length > 0 && (
          <div>
            <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              {t("recentPages")}
            </div>
            <ul className="mt-0.5 flex flex-col gap-0.5">
              {recentItems.map(({ id, labelKey, icon: Icon }) => (
                <li key={"recent-" + id}>
                  <button
                    onClick={() => onNavigate(id)}
                    title={t(labelKey)}
                    aria-label={t(labelKey)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-[var(--radius-btn)] px-3 py-1.5 text-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]",
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand-blue)]",
                    )}
                  >
                    <Icon size={15} className="shrink-0 opacity-70" />
                    <span className="flex-1 text-left">{t(labelKey)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {NAV_SECTIONS.map((section) => {
          const isCollapsed = !!collapsed[section.id];
          return (
            <div key={section.id}>
              {section.titleKey && !compact && (
                <button
                  onClick={() => toggle(section.id)}
                  aria-expanded={!isCollapsed}
                  className="flex w-full items-center justify-between rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] hover:text-[var(--text-secondary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand-blue)]"
                >
                  <span>{t(section.titleKey)}</span>
                  <ChevronDown
                    size={12}
                    className={cn("transition-transform", isCollapsed && "-rotate-90")}
                  />
                </button>
              )}
              {(!isCollapsed || compact) && (
                <ul className="mt-0.5 flex flex-col gap-0.5">
                  {section.items.map(({ id, labelKey, icon: Icon }) => (
                    <li key={id}>
                      <button
                        onClick={() => onNavigate(id)}
                        aria-current={active === id ? "page" : undefined}
                        title={t(labelKey)}
                        aria-label={t(labelKey)}
                        className={cn(
                          "flex w-full items-center gap-3 rounded-[var(--radius-btn)] py-2 text-sm font-medium transition-colors",
                          compact ? "justify-center px-0" : "px-3",
                          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand-blue)]",
                          active === id
                            ? "bg-[var(--brand-blue)]/12 text-[var(--brand-blue)]"
                            : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]",
                        )}
                      >
                        <Icon size={17} className="shrink-0" />
                        {!compact && <span className="flex-1 text-left">{t(labelKey)}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      {/* Daralt / genislet */}
      <button
        onClick={toggleCompact}
        aria-label={compact ? t("sidebarExpandAria") : t("sidebarCollapseAria")}
        title={compact ? t("sidebarExpandTitle") : t("sidebarCollapseTitle")}
        className={cn(
          "mt-2 flex items-center gap-2 rounded-[var(--radius-btn)] py-2 text-sm text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]",
          compact ? "justify-center px-0" : "px-3",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand-blue)]",
        )}
      >
        {compact ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        {!compact && <span>{t("sidebarCollapseTitle")}</span>}
      </button>
    </nav>
  );
}
