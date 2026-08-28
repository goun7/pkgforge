import { useEffect, useState } from "react";
import { PackageOpen, ArrowLeftRight, PackageCheck } from "lucide-react";
import { Dialog } from "./ui/Dialog";
import { Button } from "./ui/Button";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

const SEEN_KEY = "pkgforge.onboarding.seen";

/** Ilk calistirmada gosterilen kisa karsilama rehberi (9.1). */
export function Onboarding() {
  const t = tFor(useLang());
  const [open, setOpen] = useState(() => {
    try {
      return !localStorage.getItem(SEEN_KEY);
    } catch {
      return false;
    }
  });

  // Faz 8 (2.3): komut paletinden yeniden acilabilme.
  useEffect(() => {
    const reopen = () => setOpen(true);
    window.addEventListener("pkgforge:reopen-onboarding", reopen);
    return () => window.removeEventListener("pkgforge:reopen-onboarding", reopen);
  }, []);

  const close = () => {
    try {
      localStorage.setItem(SEEN_KEY, "1");
    } catch {
      // localStorage yoksa sessizce gec
    }
    setOpen(false);
  };

  if (!open) return null;

  const steps = [
    { icon: PackageOpen, title: t("onbStep1Title"), desc: t("onbStep1Desc") },
    { icon: ArrowLeftRight, title: t("onbStep2Title"), desc: t("onbStep2Desc") },
    { icon: PackageCheck, title: t("onbStep3Title"), desc: t("onbStep3Desc") },
  ];

  return (
    <Dialog open={open} onClose={close} title={t("onbTitle")}>
      <p className="mb-4 text-sm text-[var(--text-secondary)]">{t("onbIntro")}</p>
      <div className="space-y-3">
        {steps.map(({ icon: Icon, title, desc }, i) => (
          <div key={i} className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--brand-blue)]/12">
              <Icon size={18} className="text-[var(--brand-blue)]" />
            </div>
            <div>
              <p className="text-sm font-semibold text-[var(--text-primary)]">{title}</p>
              <p className="text-xs text-[var(--text-secondary)]">{desc}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-5 flex justify-end">
        <Button variant="primary" onClick={close}>
          {t("onbStart")}
        </Button>
      </div>
    </Dialog>
  );
}
