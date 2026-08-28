import { Info } from "lucide-react";

/** Baglam ici yardim: uzerine gelince/odaklaninca aciklama balonu (9.2). */
export function InfoTip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex items-center">
      <Info
        size={13}
        tabIndex={0}
        aria-label={text}
        className="cursor-help text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
      />
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1.5 hidden w-60 -translate-x-1/2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2 text-xs font-normal normal-case tracking-normal text-[var(--text-secondary)] shadow-[var(--shadow-md)] group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
  );
}
