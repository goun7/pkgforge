import { useMemo, useState } from "react";
import type { DepGraphData, DepNode } from "../lib/types";

interface DepGraphProps {
  data: DepGraphData;
  width?: number;
  height?: number;
}

interface Positioned {
  node: DepNode;
  x: number;
  y: number;
}

/**
 * Pure-SVG radial dependency graph. No external libs.
 * Root at center; dependencies laid out in concentric rings by BFS depth.
 * Node colors: installed=green, missing=red, foreign=amber.
 */
export function DepGraph({ data, width = 640, height = 480 }: DepGraphProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  const { positioned, edges } = useMemo(() => {
    const names = Object.keys(data.nodes);
    if (names.length === 0) return { positioned: [] as Positioned[], edges: [] as [string, string][] };

    // BFS depth from root
    const depth = new Map<string, number>();
    const root = data.root && data.nodes[data.root] ? data.root : names[0];
    depth.set(root, 0);
    const queue = [root];
    while (queue.length) {
      const cur = queue.shift()!;
      const d = depth.get(cur)!;
      for (const dep of data.nodes[cur]?.deps ?? []) {
        if (!depth.has(dep) && data.nodes[dep]) {
          depth.set(dep, d + 1);
          queue.push(dep);
        }
      }
    }
    // any unreached nodes get depth 1
    for (const n of names) if (!depth.has(n)) depth.set(n, 1);

    // group by depth ring
    const rings = new Map<number, string[]>();
    for (const [name, d] of depth) {
      if (!rings.has(d)) rings.set(d, []);
      rings.get(d)!.push(name);
    }

    const cx = width / 2;
    const cy = height / 2;
    const maxDepth = Math.max(...rings.keys());
    const ringStep = Math.min(width, height) / 2 / (maxDepth + 1.5);

    const pos = new Map<string, Positioned>();
    for (const [d, members] of rings) {
      if (d === 0) {
        const n = members[0];
        pos.set(n, { node: data.nodes[n], x: cx, y: cy });
        continue;
      }
      const r = d * ringStep + 40;
      members.forEach((n, i) => {
        const angle = (2 * Math.PI * i) / members.length - Math.PI / 2;
        pos.set(n, {
          node: data.nodes[n],
          x: cx + r * Math.cos(angle),
          y: cy + r * Math.sin(angle),
        });
      });
    }

    const edgeList: [string, string][] = [];
    for (const [src, node] of Object.entries(data.nodes)) {
      for (const dep of node.deps) {
        if (data.nodes[dep]) edgeList.push([src, dep]);
      }
    }

    return { positioned: [...pos.values()], edges: edgeList };
  }, [data, width, height]);

  if (Object.keys(data.nodes).length === 0) {
    return <p className="text-sm text-[var(--text-muted)]">Grafik verisi yok.</p>;
  }

  const colorFor = (n: DepNode): string => {
    if (!n.is_installed) return "var(--danger)";
    if (n.is_foreign) return "var(--warning)";
    return "var(--success)";
  };

  const posMap = new Map(positioned.map((p) => [p.node.name, p]));
  const hoveredNode = hovered ? data.nodes[hovered] : null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
        <span>Toplam: {data.stats.total}</span>
        <span>Kurulu: {data.stats.installed}</span>
        <span>Eksik: {data.stats.missing}</span>
        <span>Yabancı: {data.stats.foreign}</span>
        <span>Derinlik: {data.stats.max_depth}</span>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full rounded-md border border-[var(--border-subtle)] bg-[var(--bg-base)]"
        role="img"
        aria-label="Bağımlılık grafiği"
      >
        {/* edges */}
        {edges.map(([src, dst]) => {
          const a = posMap.get(src);
          const b = posMap.get(dst);
          if (!a || !b) return null;
          return (
            <line
              key={`${src}->${dst}`}
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke="var(--border-strong)" strokeWidth={1} opacity={0.5}
            />
          );
        })}
        {/* nodes */}
        {positioned.map(({ node, x, y }) => (
          <g
            key={node.name}
            onMouseEnter={() => setHovered(node.name)}
            onMouseLeave={() => setHovered(null)}
            style={{ cursor: "pointer" }}
          >
            <circle cx={x} cy={y} r={node.name === data.root ? 14 : 9} fill={colorFor(node)} opacity={0.9} />
            <text
              x={x}
              y={y + (node.name === data.root ? 26 : 20)}
              textAnchor="middle"
              fontSize={10}
              fill="var(--text-secondary)"
            >
              {node.name}
            </text>
          </g>
        ))}
      </svg>
      {hoveredNode && (
        <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2 text-xs">
          <span className="font-medium text-[var(--text-primary)]">{hoveredNode.name}</span>
          {hoveredNode.version && <span className="ml-2 text-[var(--text-muted)]">{hoveredNode.version}</span>}
          <span className="ml-2 text-[var(--text-muted)]">
            {hoveredNode.is_installed ? "kurulu" : "eksik"}{hoveredNode.is_foreign ? " · yabancı" : ""}
          </span>
          {hoveredNode.deps.length > 0 && (
            <span className="ml-2 text-[var(--text-muted)]">→ {hoveredNode.deps.join(", ")}</span>
          )}
        </div>
      )}
    </div>
  );
}
