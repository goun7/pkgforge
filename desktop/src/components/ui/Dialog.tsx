import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "../../lib/utils";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
}

/** Dialog icinde odaklanabilir ogeler (odak tupu icin). */
const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Minimal modal dialog: Escape, backdrop tiklama ve odak tupu (focus trap). */
export function Dialog({ open, onClose, title, children, className }: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const lastFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    lastFocused.current = document.activeElement as HTMLElement | null;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusables = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !panel.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);

    // Acilinca odağı panele (veya ilk odaklanabilir ogeye) tasir.
    const timer = setTimeout(() => {
      const panel = panelRef.current;
      if (!panel) return;
      const first = panel.querySelector<HTMLElement>(FOCUSABLE);
      (first ?? panel).focus();
    }, 0);

    return () => {
      window.removeEventListener("keydown", onKey);
      clearTimeout(timer);
      // Kapaninca odak, dialog'u acan ogeye geri doner.
      lastFocused.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "w-full max-w-lg rounded-[var(--radius-modal)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--shadow-lg)] focus:outline-none",
          className,
        )}
      >
        {title && (
          <div className="flex items-center justify-between px-6 pt-5">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h2>
            <button
              onClick={onClose}
              aria-label="Kapat"
              className="rounded-md p-1 text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
            >
              <X size={18} />
            </button>
          </div>
        )}
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}
