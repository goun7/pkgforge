import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

// Faz 8: test izolasyonu — her test oncesi depolama temizlenir, boylece
// kalici sayfa state'i / ayarlar testler arasi sizinti yapmaz.
beforeEach(() => {
  try {
    sessionStorage.clear();
    localStorage.clear();
  } catch {
    /* depolama yok */
  }
});

// jsdom does not implement scrollIntoView; stub it for components that
// auto-scroll (LogViewer).
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
