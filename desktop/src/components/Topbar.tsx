import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";
import { onRpcActivity } from "../lib/rpc";

export interface TopbarProps {
  title: string;
  /** Faz 8 (3.3): basligin altinda gorunen kisa sayfa aciklamasi. */
  subtitle?: string;
  onSearchClick?: () => void;
  right?: React.ReactNode;
}

export function Topbar({ title, subtitle, onSearchClick, right }: TopbarProps) {
  const t = tFor(useLang());
  // Faz 8 (3.4): global RPC aktivite cizgisi.
  const [active, setActive] = useState(false);
  useEffect(() => onRpcActivity(setActive), []);
  return (
    <header className="relative flex h-14 shrink-0 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-5">
      <div className="min-w-0">
        <h1 className="truncate text-lg font-bold leading-tight tracking-tight text-[var(--text-primary)]">{title}</h1>
        {subtitle && <p className="truncate text-[11px] leading-tight text-[var(--text-muted)]">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        {onSearchClick && (
          <button
            onClick={onSearchClick}
            aria-label={t("topbarSearchAria")}
            className="flex items-center gap-2 rounded-[var(--radius-btn)] border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
          >
            <Search size={13} />
            <span>{t("topbarSearch")}</span>
            <kbd
              className="rounded bg-[var(--bg-base)] px-1.5 py-0.5 text-[10px]"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              ⌘K
            </kbd>
          </button>
        )}
        {right}
      </div>
      {active && (
        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 h-0.5 overflow-hidden"
          aria-hidden="true"
        >
          <div className="rpc-activity h-full w-1/3 rounded-full bg-[var(--brand-blue)]" />
        </div>
      )}
    </header>
  );
}
