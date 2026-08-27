import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { Sidebar } from "../Sidebar";

const root = process.cwd();
const tokensCss = readFileSync(join(root, "src/styles/tokens.css"), "utf8");
const indexCss = readFileSync(join(root, "src/styles/index.css"), "utf8");

describe("UX modernizasyonu — motion tokenlari", () => {
  it("tokens.css hareket sure tokenlarini tanimlar", () => {
    expect(tokensCss).toContain("--duration-fast");
    expect(tokensCss).toContain("--duration-base");
    expect(tokensCss).toContain("--duration-slow");
  });

  it("tokens.css easing tokenlarini tanimlar", () => {
    expect(tokensCss).toContain("--ease-standard");
    expect(tokensCss).toContain("--ease-decelerate");
  });

  it("index.css prefers-reduced-motion destegi icerir", () => {
    expect(indexCss).toContain("prefers-reduced-motion: reduce");
    expect(indexCss).toContain("transition-duration");
  });

  it("index.css standart gecis utility'si tanimlar", () => {
    expect(indexCss).toContain(".transition-standard");
  });
});

describe("UX modernizasyonu — klavye erisilebilirligi", () => {
  it("Sidebar nav butonlari focus-visible halkasi tasir", () => {
    const { container } = render(
      <Sidebar active="convert" onNavigate={() => {}} />,
    );
    const buttons = Array.from(container.querySelectorAll("nav button"));
    expect(buttons.length).toBeGreaterThan(0);
    for (const btn of buttons) {
      expect(btn.className).toContain("focus-visible");
    }
  });
});
