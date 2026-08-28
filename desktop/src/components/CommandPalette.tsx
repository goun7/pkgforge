import { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import { cn } from "../lib/utils";

export interface Command {
  id: string;
  label: string;
  hint?: string;
  action: () => void;
}

export interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  commands: Command[];
}

/** Ctrl+K ile acilan komut paleti: sayfa gecisi + eylemler, ok tuslariyla gezinme. */
export function CommandPalette({ open, onClose, commands }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(q));
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
        aria-label="Komut paleti"
        className="w-full max-w-lg overflow-hidden rounded-[var(--radius-modal)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-[var(--shadow-lg)]"
      >
        <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] px-4">
          <Search size={16} className="shrink-0 text-[var(--text-muted)]" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder="Komut ara veya sayfa adı yaz…"
            aria-label="Komut ara"
            className="h-12 flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none"
          />
          <kbd className="rounded bg-[var(--bg-base)] px-1.5 py-0.5 text-[10px] text-[var(--text-muted)]">Esc</kbd>
        </div>
        <ul className="max-h-72 overflow-y-auto p-2" role="listbox">
          {filtered.length === 0 && (
            <li className="px-3 py-4 text-center text-sm text-[var(--text-muted)]">Sonuç yok</li>
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
