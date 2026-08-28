import { useEffect, useRef } from "react";
import { onSidecarStatus } from "../lib/rpc";
import { useToast } from "./ui/Toast";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

/** Faz 8 (8.3): sidecar kopunca/duzelince kullaniciyi bilgilendirir. */
export function SidecarGuard() {
  const { toast } = useToast();
  const t = tFor(useLang());
  const down = useRef(false);

  useEffect(() => {
    const unsub = onSidecarStatus((ok) => {
      if (!ok && !down.current) {
        down.current = true;
        toast("warning", t("sidecarDown"));
      } else if (ok && down.current) {
        down.current = false;
        toast("success", t("sidecarRecovered"));
      }
    });
    return unsub;
  }, [toast, t]);

  return null;
}
