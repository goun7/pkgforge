import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrollIntoView; stub it for components that
// auto-scroll (LogViewer).
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
