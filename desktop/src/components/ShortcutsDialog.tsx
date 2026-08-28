import { useEffect, useState } from "react";
import { Dialog } from "./ui/Dialog";
import { useLang } from "../lib/lang";
import { tFor, type I18nKey } from "../lib/i18n";

/** Faz 9 (5.1): klavye kisayollari yardim katmani.
 *  Komut paletinden, topbar'dan veya Ctrl+/ ile acilir
 *  ("pkgforge:open-shortcuts" olayi). */
const ROWS: { keys: string; labelKey: I18nKey }[] = [
  { keys: "Ctrl/⌘ + K", labelKey: "shortcutsCmd" },
  { keys: "Alt + 1…9", labelKey: "shortcutsPages" },
  { keys: "Ctrl/⌘ + /", labelKey: "shortcutsHelp" },
  { keys: "↑ ↓ Enter", labelKey: "shortcutsPaletteNav" },
  { keys: "Esc", labelKey: "shortcutsClose" },
];

export function ShortcutsDialog() {
  const t = tFor(useLang());
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener("pkgforge:open-shortcuts", handler);
    return () => window.removeEventListener("pkgforge:open-shortcuts", handler);
  }, []);

  return (
    <Dialog open={open} onClose={() => setOpen(false)} title={t("shortcutsTitle")} className="max-w-md">
      <ul className="space-y-2.5">
        {ROWS.map((r) => (
          <li key={r.keys} className="flex items-center justify-between gap-4 text-sm">
            <span className="text-[var(--text-secondary)]">{t(r.labelKey)}</span>
            <kbd className="shrink-0 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-base)] px-2 py-1 font-mono text-xs text-[var(--text-primary)]">
              {r.keys}
            </kbd>
          </li>
        ))}
      </ul>
    </Dialog>
  );
}
