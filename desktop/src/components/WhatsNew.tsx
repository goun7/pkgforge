import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { Dialog } from "./ui/Dialog";
import { Button } from "./ui/Button";
import { useLang } from "../lib/lang";
import { tFor, type I18nKey } from "../lib/i18n";

const VERSION = "2.0.0";
const SEEN_KEY = "pkgforge.whatsnew.seen";

/** Faz 8 (9.3): uygulama surumu degistiginde yenilikleri bir kez gosterir. */
export function WhatsNew() {
  const t = tFor(useLang());
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      // Ilk acilista Onboarding gosterilir; WhatsNew sadece geri donen
      // kullaniciya (onboarding gorulmus) ve surum degismisse acilir.
      const onboarded = localStorage.getItem("pkgforge.onboarding.seen");
      if (onboarded && localStorage.getItem(SEEN_KEY) !== VERSION) setOpen(true);
    } catch {
      /* depolama yok */
    }
  }, []);

  const close = () => {
    try {
      localStorage.setItem(SEEN_KEY, VERSION);
    } catch {
      /* depolama yok */
    }
    setOpen(false);
  };

  if (!open) return null;

  const items: I18nKey[] = ["wnItem1", "wnItem2", "wnItem3", "wnItem4"];

  return (
    <Dialog open={open} onClose={close} title={t("whatsNewTitle")}>
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--brand-blue)]/12">
          <Sparkles size={20} className="text-[var(--brand-blue)]" />
        </div>
        <span className="text-xs font-medium text-[var(--text-muted)]">v{VERSION}</span>
      </div>
      <ul className="mb-5 space-y-2">
        {items.map((k) => (
          <li key={k} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--brand-blue)]" />
            {t(k)}
          </li>
        ))}
      </ul>
      <div className="flex justify-end">
        <Button variant="primary" onClick={close}>
          {t("whatsNewClose")}
        </Button>
      </div>
    </Dialog>
  );
}
