import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DepGraph } from "../DepGraph";
import type { DepGraphData } from "../../lib/types";

const SAMPLE: DepGraphData = {
  root: "mypkg",
  nodes: {
    mypkg: { name: "mypkg", version: "1.0", deps: ["glibc", "openssl"], needed_by: [], is_installed: true, is_foreign: false },
    glibc: { name: "glibc", version: "2.39", deps: [], needed_by: ["mypkg"], is_installed: true, is_foreign: false },
    openssl: { name: "openssl", version: "3.2", deps: [], needed_by: ["mypkg"], is_installed: false, is_foreign: false },
  },
  stats: { total: 3, installed: 2, missing: 1, foreign: 0, max_depth: 1 },
  mermaid: "",
  warnings: [],
};

describe("DepGraph component", () => {
  it("renders an SVG", () => {
    const { container } = render(<DepGraph data={SAMPLE} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders all node labels", () => {
    render(<DepGraph data={SAMPLE} />);
    expect(screen.getByText("mypkg")).toBeInTheDocument();
    expect(screen.getByText("glibc")).toBeInTheDocument();
    expect(screen.getByText("openssl")).toBeInTheDocument();
  });

  it("shows stats summary", () => {
    render(<DepGraph data={SAMPLE} />);
    expect(screen.getByText(/Toplam: 3/)).toBeInTheDocument();
  });

  it("renders empty state for empty graph", () => {
    render(<DepGraph data={{ root: "", nodes: {}, stats: { total: 0, installed: 0, missing: 0, foreign: 0, max_depth: 0 }, mermaid: "", warnings: [] }} />);
    expect(screen.getByText(/grafik verisi yok/i)).toBeInTheDocument();
  });
});
