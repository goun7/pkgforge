import { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import { cn } from "../lib/utils";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

/** Faz 8 (2.4): basit fuzzy (alt dizi) eslesme + puanlama. */
function fuzzyScore(label: string, q: string): number {
  const hay = label.toLowerCase();
  if (hay.includes(q)) return 1000 - hay.indexOf(q);
  let hi = 0;
  let gap = 0;
  for (let qi = 0; qi < q.length; qi++) {
    const found = hay.indexOf(q[qi], hi);
    if (found === -1) return -1;
    gap += found - hi;
    hi = found + 1;
  }
  return 500 - gap;
}

export interface Command {
  id: string;
  label: string;
  hint?: string;
  action: () => void;
}

/** Faz 9 (5.8): son kullanilan komutlarin id'leri (en yeni basta, max 5). */
const RECENT_KEY = "pkgforge.palette.recent";
function loadRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}
function saveRecent(id: string): void {
  try {
    const cur = loadRecent().filter((x) => x !== id);
    cur.unshift(id);
    localStorage.setItem(RECENT_KEY, JSON.stringify(cur.slice(0, 5)));
  } catch {
    /* depolama yok */
  }
}

export interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  commands: Command[];
}

/** Ctrl+K ile acilan komut paleti: sayfa gecisi + eylemler, ok tuslariyla gezinme. */
export function CommandPalette({ open, onClose, commands }: CommandPaletteProps) {
  const t = tFor(useLang());
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      // Faz 9 (5.8): sorgu yokken son kullanilan komutlar üste sabitlenir.
      const recent = loadRecent();
      if (recent.length === 0) return commands;
      return [...commands].sort((a, b) => {
        const ai = recent.indexOf(a.id);
        const bi = recent.indexOf(b.id);
        if (ai === -1 && bi === -1) return 0;
        if (ai === -1) return 1;
        if (bi === -1) return -1;
        return ai - bi;
      });
    }
    return commands
      .map((c) => ({ c, score: fuzzyScore(c.label, q) }))
      .filter((x) => x.score >= 0)
      .sort((a, b) => b.score - a.score)
      .map((x) => x.c);
  }, [query, commands]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setIndex(0);
      const t = setTimeout(() => inputRef.current?.focus(), 0);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => {
    setIndex(0);
  }, [query]);

  if (!open) return null;

  const run = (cmd: Command) => {
    saveRecent(cmd.id);
    cmd.action();
    onClose();
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      setIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[index]) {
      e.preventDefault();
      run(filtered[index]);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center bg-black/60 p-4 pt-[15vh]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("cmdPaletteAria")}
        className="w-full max-w-lg overflow-hidden rounded-[var(--radius-modal)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-[var(--shadow-lg)]"
      >
        <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] px-4">
          <Search size={16} className="shrink-0 text-[var(--text-muted)]" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder={t("cmdPlaceholder")}
            aria-label={t("cmdSearchAria")}
            className="h-12 flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none"
          />
          <kbd className="rounded bg-[var(--bg-base)] px-1.5 py-0.5 text-[10px] text-[var(--text-muted)]">Esc</kbd>
        </div>
        <ul className="max-h-72 overflow-y-auto p-2" role="listbox">
          {filtered.length === 0 && (
            <li className="px-3 py-4 text-center text-sm text-[var(--text-muted)]">{t("cmdNoResult")}</li>
          )}
          {filtered.map((cmd, i) => (
            <li key={cmd.id} role="option" aria-selected={i === index}>
              <button
                onClick={() => run(cmd)}
                onMouseEnter={() => setIndex(i)}
                className={cn(
                  "flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm",
                  i === index
                    ? "bg-[var(--brand-blue)]/12 text-[var(--brand-blue)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]",
                )}
              >
                <span>{cmd.label}</span>
                {cmd.hint && <span className="text-xs text-[var(--text-muted)]">{cmd.hint}</span>}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
