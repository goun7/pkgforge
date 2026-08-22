import { Search } from "lucide-react";

export interface TopbarProps {
  title: string;
  onSearchClick?: () => void;
  right?: React.ReactNode;
}

export function Topbar({ title, onSearchClick, right }: TopbarProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-5">
      <h1 className="text-base font-semibold text-[var(--text-primary)]">{title}</h1>
      <div className="flex items-center gap-3">
        {onSearchClick && (
          <button
            onClick={onSearchClick}
            aria-label="Ara"
            className="flex items-center gap-2 rounded-[var(--radius-btn)] border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
          >
            <Search size={13} />
            <span>Ara…</span>
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
    </header>
  );
}
