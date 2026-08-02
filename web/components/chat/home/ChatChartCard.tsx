"use client";

import { useEffect, useRef } from "react";

type ChartData =
  | { type: "scorecard"; data: { f1: number; precision: number; recall: number; passed: boolean } }
  | { type: "radar"; data: { labels: string[]; values: number[] } }
  | { type: "progress"; data: { completed: number; total: number; modules: { name: string; done: number; total: number }[] } }
  | { type: "graph"; data: { nodes: { id: string; label: string; status: string }[]; edges: { source: string; target: string }[] } };

export function ChatChartCard({ chart }: { chart: ChartData }) {
  if (chart.type === "scorecard") {
    const { f1, precision, recall, passed } = chart.data;
    return (
      <div className="my-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
        <div className="mb-2 flex items-center gap-2">
          <span className={`text-lg font-bold ${passed ? "text-emerald-500" : "text-rose-500"}`}>
            F1 = {f1.toFixed(2)}
          </span>
          <span className={`rounded px-1.5 py-0.5 text-[10px] ${passed ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"}`}>
            {passed ? "达标" : "待加强"}
          </span>
        </div>
        <div className="space-y-1 text-xs text-[var(--muted-foreground)]">
          <div>Precision: {(precision * 100).toFixed(0)}%</div>
          <div>Recall: {(recall * 100).toFixed(0)}%</div>
        </div>
      </div>
    );
  }

  if (chart.type === "radar") {
    return <RadarCard labels={chart.data.labels} values={chart.data.values} />;
  }

  if (chart.type === "progress") {
    const { completed, total, modules } = chart.data;
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    return (
      <div className="my-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-semibold">学习进度</span>
          <span className="text-[var(--muted-foreground)]">{completed}/{total} ({pct}%)</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
          <div className="h-full rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
        </div>
        {modules.length > 0 && (
          <div className="mt-2 space-y-1">
            {modules.map((m) => (
              <div key={m.name} className="flex items-center gap-2 text-[10px] text-[var(--muted-foreground)]">
                <span className="w-16 truncate">{m.name}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--border)]">
                  <div className="h-full rounded-full bg-emerald-500" style={{ width: `${m.total ? (m.done / m.total) * 100 : 0}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (chart.type === "graph") {
    return <GraphCard nodes={chart.data.nodes} edges={chart.data.edges} />;
  }

  return null;
}

function RadarCard({ labels, values }: { labels: string[]; values: number[] }) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    let chart: any;
    import("chart.js/auto").then(({ default: Chart }) => {
      if (!ref.current) return;
      chart = new Chart(ref.current, {
        type: "radar",
        data: {
          labels,
          datasets: [{ data: values, backgroundColor: "rgba(59,130,246,0.2)", borderColor: "#3b82f6" }],
        },
        options: { scales: { r: { min: 0, max: 100 } } },
      });
    });
    return () => chart?.destroy();
  }, [labels, values]);
  return (
    <div className="my-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-2">
      <canvas ref={ref} />
    </div>
  );
}

function GraphCard({ nodes, edges }: { nodes: { id: string; label: string; status: string }[]; edges: { source: string; target: string }[] }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    let cy: any;
    import("cytoscape").then((m) => {
      if (!ref.current) return;
      const cytoscape = m.default ?? m;
      cy = cytoscape({
        container: ref.current,
        elements: [
          ...nodes.map((n) => ({ data: { id: n.id, label: n.label, status: n.status } })),
          ...edges.map((e, i) => ({ data: { id: `e${i}`, source: e.source, target: e.target } })),
        ],
        style: [
          { selector: "node", style: { label: "data(label)", "font-size": "9px", "text-valign": "bottom", "text-wrap": "wrap", "text-max-width": "80px" } },
          { selector: 'node[status = "missing"]', style: { "background-color": "#f59e0b" } },
          { selector: 'node[status = "struggling"]', style: { "background-color": "#ef4444" } },
          { selector: 'node[status = "affected"]', style: { "background-color": "#8b5cf6" } },
          { selector: 'node[status = "target"]', style: { "background-color": "#3b82f6" } },
          { selector: "edge", style: { "line-color": "#cbd5e1", "target-arrow-color": "#cbd5e1", "target-arrow-shape": "triangle" } },
        ],
        layout: { name: "breadthfirst", padding: 10 },
      });
    });
    return () => cy?.destroy();
  }, [nodes, edges]);
  return <div ref={ref} className="my-2 h-40 rounded-xl border border-[var(--border)] bg-[var(--card)]" />;
}
