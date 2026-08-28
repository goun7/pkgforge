import { call } from "./rpc";

export type Theme = "dark" | "light" | "system" | "oled";
export type ResolvedTheme = "dark" | "light" | "oled";

/** "system" tercihini isletim sistemi renk semasina gore cozer. */
export function resolveTheme(theme: string): ResolvedTheme {
  if (theme === "system") {
    try {
      return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    } catch {
      return "dark";
    }
  }
  if (theme === "oled") return "oled";
  return theme === "light" ? "light" : "dark";
}

/** Faz 8 (10.4): "system" seciliyken OS tema degisikligini canli izle. */
let systemThemeCleanup: (() => void) | null = null;
function watchSystemTheme(theme: string): void {
  if (systemThemeCleanup) {
    systemThemeCleanup();
    systemThemeCleanup = null;
  }
  if (theme !== "system") return;
  try {
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const handler = () => {
      document.documentElement.setAttribute("data-theme", resolveTheme("system"));
    };
    mq.addEventListener("change", handler);
    systemThemeCleanup = () => mq.removeEventListener("change", handler);
  } catch {
    /* matchMedia yok */
  }
}

/** Temayi uygular; degisim sirasinda kisa bir gecis sinifi ekler. */
export function applyTheme(theme: string): void {
  const root = document.documentElement;
  root.classList.add("theme-switching");
  root.setAttribute("data-theme", resolveTheme(theme));
  window.setTimeout(() => root.classList.remove("theme-switching"), 400);
  watchSystemTheme(theme);
}

/** Baslangicta kayitli temayi uygular (sidecar hazir degilse sessizce gecer). */
export async function loadTheme(): Promise<void> {
  try {
    const s = await call<{ theme?: unknown }>("settings.get");
    if (s && typeof s.theme === "string") applyTheme(s.theme);
  } catch {
    // sidecar henuz hazir degil — varsayilan tema kalir
  }
}

/** Faz 10 (5.1): vurgu rengi kisisellestirme. UI-only oldugu icin backend
 *  ayarlarina degil localStorage'a yazilir; CSS [data-accent] ile uygulanir. */
export type Accent = "blue" | "green" | "purple" | "orange" | "rose";
export const ACCENTS: Accent[] = ["blue", "green", "purple", "orange", "rose"];
const ACCENT_KEY = "pkgforge.accent";

export function applyAccent(accent: string): void {
  const root = document.documentElement;
  if (!ACCENTS.includes(accent as Accent) || accent === "blue") {
    root.removeAttribute("data-accent");
  } else {
    root.setAttribute("data-accent", accent);
  }
  try {
    localStorage.setItem(ACCENT_KEY, accent);
  } catch {
    /* depolama yok */
  }
}

/** Baslangicta kayitli vurgu rengini uygular (senkron, sidecar gerektirmez). */
export function loadAccentLocal(): void {
  try {
    const a = localStorage.getItem(ACCENT_KEY);
    if (a) applyAccent(a);
  } catch {
    /* depolama yok */
  }
}

/** Kayitli vurgu rengini dondurur (Settings secici durumu icin). */
export function getAccentLocal(): Accent {
  try {
    const a = localStorage.getItem(ACCENT_KEY);
    if (a && ACCENTS.includes(a as Accent)) return a as Accent;
  } catch {
    /* depolama yok */
  }
  return "blue";
}
