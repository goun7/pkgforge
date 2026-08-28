import { useEffect, useState } from "react";
import { Languages, Moon, Sun, Wifi, WifiOff, Loader2 } from "lucide-react";
import { useLang, setLang } from "../lib/lang";
import { applyTheme, resolveTheme } from "../lib/theme";
import { call } from "../lib/rpc";
import { cn } from "../lib/utils";

const iconBtn =
  "flex items-center gap-1.5 rounded-[var(--radius-btn)] px-2 py-1.5 text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand-blue)]";

/** Topbar sag tarafi: sidecar durumu + dil ve tema degistiriciler. */
export function TopbarActions() {
  const lang = useLang();
  const [theme, setThemeState] = useState<string>(
    () => document.documentElement.getAttribute("data-theme") ?? "dark",
  );
  const [online, setOnline] = useState<boolean | null>(null);

  // Sidecar baglanti durumunu periyodik olarak yokla.
  useEffect(() => {
    let alive = true;
    const ping = async () => {
      try {
        await call("settings.get");
        if (alive) setOnline(true);
      } catch {
        if (alive) setOnline(false);
      }
    };
    void ping();
    const iv = setInterval(() => void ping(), 15000);
    return () => {
      alive = false;
      clearInterval(iv);
    };
  }, []);

  const toggleLang = async () => {
    const next = lang === "tr" ? "en" : "tr";
    setLang(next);
    try {
      await call("settings.set", { language: next });
    } catch {
      // sidecar hazir degil — yalnizca canli magaza degisti
    }
  };

  const toggleTheme = async () => {
    const cur = resolveTheme(theme);
    const next = cur === "dark" ? "light" : "dark";
    applyTheme(next);
    setThemeState(next);
    try {
      await call("settings.set", { theme: next });
    } catch {
      // sidecar hazir degil — tema yine de uygulandi
    }
  };

  return (
    <div className="flex items-center gap-1">
      <span
        title={online === null ? "Sidecar bağlanıyor…" : online ? "Sidecar bağlı" : "Sidecar bağlı değil"}
        aria-label={online === null ? "Sidecar bağlanıyor" : online ? "Sidecar bağlı" : "Sidecar bağlı değil"}
        className={cn(
          "mr-1 flex items-center",
          online === null
            ? "text-[var(--text-muted)]"
            : online
              ? "text-[var(--success)]"
              : "text-[var(--danger)]",
        )}
      >
        {online === null ? (
          <Loader2 size={15} className="animate-spin" />
        ) : online ? (
          <Wifi size={15} />
        ) : (
          <WifiOff size={15} />
        )}
      </span>
      <button onClick={() => void toggleLang()} aria-label="Dili değiştir" title="Dil" className={iconBtn}>
        <Languages size={15} />
        <span className="text-xs font-semibold uppercase">{lang}</span>
      </button>
      <button onClick={() => void toggleTheme()} aria-label="Temayı değiştir" title="Tema" className={iconBtn}>
        {resolveTheme(theme) === "light" ? <Moon size={15} /> : <Sun size={15} />}
      </button>
    </div>
  );
}
