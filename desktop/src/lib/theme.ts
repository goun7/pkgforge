import { call } from "./rpc";

export type Theme = "dark" | "light" | "system";

/** "system" tercihini isletim sistemi renk semasina gore cozer. */
export function resolveTheme(theme: string): "dark" | "light" {
  if (theme === "system") {
    try {
      return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    } catch {
      return "dark";
    }
  }
  return theme === "light" ? "light" : "dark";
}

/** Temayi uygular; degisim sirasinda kisa bir gecis sinifi ekler. */
export function applyTheme(theme: string): void {
  const root = document.documentElement;
  root.classList.add("theme-switching");
  root.setAttribute("data-theme", resolveTheme(theme));
  window.setTimeout(() => root.classList.remove("theme-switching"), 400);
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
