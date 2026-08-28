import { useEffect, useState } from "react";
import { ShieldCheck, Network, Camera, Command, Compass } from "lucide-react";
import { Dialog } from "./ui/Dialog";
import { Button } from "./ui/Button";
import { useLang } from "../lib/lang";
import { tFor, type I18nKey } from "../lib/i18n";

/** Faz 8 (9.1): gelismis ozellikler icin cok adimli rehber tur.
 *  Komut paletinden veya "pkgforge:open-tour" olayiyla acilir. */
const TOUR_STEPS: { icon: typeof Compass; titleKey: I18nKey; descKey: I18nKey }[] = [
  { icon: ShieldCheck, titleKey: "tourStep1Title", descKey: "tourStep1Desc" },
  { icon: Network, titleKey: "tourStep2Title", descKey: "tourStep2Desc" },
  { icon: Camera, titleKey: "tourStep3Title", descKey: "tourStep3Desc" },
  { icon: Command, titleKey: "tourStep4Title", descKey: "tourStep4Desc" },
];

export function FeatureTour() {
  const t = tFor(useLang());
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    const handler = () => {
      setStep(0);
      setOpen(true);
    };
    window.addEventListener("pkgforge:open-tour", handler);
    return () => window.removeEventListener("pkgforge:open-tour", handler);
  }, []);

  const close = () => setOpen(false);
  const isLast = step === TOUR_STEPS.length - 1;
  const Step = TOUR_STEPS[step].icon;

  return (
    <Dialog open={open} onClose={close} title={t("tourTitle")}>
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--brand-blue)]/12">
          <Step size={22} className="text-[var(--brand-blue)]" />
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t(TOUR_STEPS[step].titleKey)}</h3>
          <p className="text-[11px] text-[var(--text-muted)]">
            {step + 1} / {TOUR_STEPS.length} {t("tourStepOf")}
          </p>
        </div>
      </div>
      <p className="mb-5 text-sm leading-relaxed text-[var(--text-secondary)]">{t(TOUR_STEPS[step].descKey)}</p>
      {/* adim noktaciklari */}
      <div className="mb-4 flex justify-center gap-1.5" aria-hidden="true">
        {TOUR_STEPS.map((_, i) => (
          <span
            key={i}
            className={
              "h-1.5 rounded-full transition-all " +
              (i === step ? "w-5 bg-[var(--brand-blue)]" : "w-1.5 bg-[var(--border-strong)]")
            }
          />
        ))}
      </div>
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={close}>
          {t("tourSkip")}
        </Button>
        <div className="flex gap-2">
          {step > 0 && (
            <Button variant="secondary" size="sm" onClick={() => setStep((s) => s - 1)}>
              {t("tourPrev")}
            </Button>
          )}
          <Button
            variant="primary"
            size="sm"
            onClick={() => (isLast ? close() : setStep((s) => s + 1))}
          >
            {isLast ? t("tourDone") : t("tourNext")}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
