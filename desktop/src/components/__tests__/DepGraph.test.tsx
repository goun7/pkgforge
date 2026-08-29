import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DepGraph } from "../DepGraph";
import type { DepGraphData, DepNode } from "../../lib/types";

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

const mkNode = (name: string, over: Partial<DepNode> = {}): DepNode => ({
  name,
  version: "1.0",
  deps: [],
  needed_by: [],
  is_installed: true,
  is_foreign: false,
  ...over,
});

/** Her <g> icin dugum adi → circle fill eslemesi. */
function nodeFills(container: HTMLElement): Record<string, string> {
  const out: Record<string, string> = {};
  for (const g of Array.from(container.querySelectorAll("svg g"))) {
    const name = g.querySelector("text")?.textContent ?? "";
    out[name] = g.querySelector("circle")?.getAttribute("fill") ?? "";
  }
  return out;
}

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

describe("DepGraph layout & edges", () => {
  it("renders one edge line per dependency with viewBox and aria label", () => {
    const { container } = render(<DepGraph data={SAMPLE} />);
    expect(container.querySelectorAll("line")).toHaveLength(2);
    const svg = container.querySelector("svg") as SVGSVGElement;
    expect(svg).toHaveAttribute("viewBox", "0 0 640 480");
    expect(screen.getByRole("img", { name: "Bağımlılık grafiği" })).toBeInTheDocument();
  });

  it("lays out deeper dependency chains in outer rings", () => {
    const data: DepGraphData = {
      root: "a",
      nodes: {
        a: mkNode("a", { deps: ["b"] }),
        b: mkNode("b", { deps: ["c"] }),
        c: mkNode("c"),
      },
      stats: { total: 3, installed: 3, missing: 0, foreign: 0, max_depth: 2 },
      mermaid: "",
      warnings: [],
    };
    const { container } = render(<DepGraph data={data} />);
    expect(container.querySelectorAll("circle")).toHaveLength(3);
    expect(container.querySelectorAll("line")).toHaveLength(2);
    expect(screen.getByText("c")).toBeInTheDocument();
  });

  it("renders unreachable orphan nodes on the first ring", () => {
    const data: DepGraphData = {
      root: "a",
      nodes: {
        a: mkNode("a", { deps: ["b"] }),
        b: mkNode("b"),
        orphan: mkNode("orphan"),
      },
      stats: { total: 3, installed: 3, missing: 0, foreign: 0, max_depth: 1 },
      mermaid: "",
      warnings: [],
    };
    const { container } = render(<DepGraph data={data} />);
    expect(container.querySelectorAll("circle")).toHaveLength(3);
    expect(screen.getByText("orphan")).toBeInTheDocument();
  });

  it("ignores dependencies that are missing from the node map", () => {
    const data: DepGraphData = {
      root: "a",
      nodes: { a: mkNode("a", { deps: ["ghost"] }) },
      stats: { total: 1, installed: 1, missing: 0, foreign: 0, max_depth: 0 },
      mermaid: "",
      warnings: [],
    };
    const { container } = render(<DepGraph data={data} />);
    expect(container.querySelectorAll("circle")).toHaveLength(1);
    expect(container.querySelectorAll("line")).toHaveLength(0);
    expect(screen.queryByText("ghost")).not.toBeInTheDocument();
  });

  it("falls back to the first node when root is empty or unknown", () => {
    // Kok dugum merkezde konumlanir (cx=width/2, cy=height/2 → 320,240).
    const atCenter = (c: HTMLElement) =>
      c.querySelector('circle[cx="320"][cy="240"]')?.closest("g")?.textContent;
    const first = render(<DepGraph data={{ ...SAMPLE, root: "" }} />);
    expect(atCenter(first.container)).toBe("mypkg");
    const second = render(<DepGraph data={{ ...SAMPLE, root: "nope" }} />);
    expect(atCenter(second.container)).toBe("mypkg");
  });

  it("draws the root node larger with its label pushed further down", () => {
    const { container } = render(<DepGraph data={SAMPLE} />);
    const rootCircle = container.querySelector('circle[r="14"]');
    expect(rootCircle?.closest("g")?.textContent).toBe("mypkg");
    // kok harici dugumler kucuk yaricapla cizilir
    expect(container.querySelectorAll('circle[r="9"]')).toHaveLength(2);
  });
});

describe("DepGraph node types & hover panel", () => {
  it("colors nodes by install/foreign state", () => {
    const data: DepGraphData = {
      root: "mypkg",
      nodes: {
        mypkg: mkNode("mypkg", { deps: ["ok", "missing", "foreign"] }),
        ok: mkNode("ok"),
        missing: mkNode("missing", { is_installed: false }),
        foreign: mkNode("foreign", { is_foreign: true }),
      },
      stats: { total: 4, installed: 3, missing: 1, foreign: 1, max_depth: 1 },
      mermaid: "",
      warnings: [],
    };
    const { container } = render(<DepGraph data={data} />);
    const fills = nodeFills(container);
    expect(fills.ok).toBe("var(--success)");
    expect(fills.missing).toBe("var(--danger)");
    expect(fills.foreign).toBe("var(--warning)");
  });

  it("shows a detail panel on hover and hides it on leave", () => {
    render(<DepGraph data={SAMPLE} />);
    const rootG = screen.getByText("mypkg").closest("g") as SVGGElement;
    fireEvent.mouseOver(rootG);
    // panel: surum + kurulu durumu + deps listesi
    expect(screen.getByText("1.0")).toBeInTheDocument();
    expect(screen.getByText("Kurulu")).toBeInTheDocument();
    expect(screen.getByText("→ glibc, openssl")).toBeInTheDocument();
    fireEvent.mouseOut(rootG);
    expect(screen.queryByText("→ glibc, openssl")).not.toBeInTheDocument();

    // eksik ama yabanci olmayan dugum: "Eksik" etiketi, yabanci eki yok
    const missingG = screen.getByText("openssl").closest("g") as SVGGElement;
    fireEvent.mouseOver(missingG);
    expect(screen.getByText("3.2")).toBeInTheDocument();
    expect(screen.getByText("Eksik")).toBeInTheDocument();
    expect(screen.queryByText(/yabancı/)).not.toBeInTheDocument();
    fireEvent.mouseOut(missingG);
    expect(screen.queryByText("3.2")).not.toBeInTheDocument();
  });

  it("marks foreign missing nodes in the hover panel and stats row", () => {
    const data: DepGraphData = {
      root: "mypkg",
      nodes: {
        mypkg: mkNode("mypkg", { deps: ["aurlib"] }),
        aurlib: mkNode("aurlib", { version: "", is_installed: false, is_foreign: true }),
      },
      stats: { total: 2, installed: 1, missing: 1, foreign: 1, max_depth: 1 },
      mermaid: "",
      warnings: [],
    };
    render(<DepGraph data={data} />);
    expect(screen.getByText(/Yabancı: 1/)).toBeInTheDocument();
    expect(screen.getByText(/Derinlik: 1/)).toBeInTheDocument();
    const g = screen.getByText("aurlib").closest("g") as SVGGElement;
    fireEvent.mouseOver(g);
    // bos surum render edilmez; deps bos oldugu icin ok listesi yok
    expect(screen.getByText(/Eksik · yabancı/)).toBeInTheDocument();
    expect(screen.queryByText(/→/)).not.toBeInTheDocument();
  });
});
