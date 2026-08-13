"use client";

import { useEffect, useRef, useState } from "react";
import { VisualizationArtifactCard, type VisualizationArtifact } from "./VisualizationArtifactCard";

export type ChartData =
  | { type: "scorecard"; data: { f1: number; precision: number; recall: number; passed: boolean } }
  | { type: "radar"; data: { labels: string[]; values: number[] } }
  | { type: "progress"; data: { completed: number; total: number; modules: { name: string; done: number; total: number }[] } }
  | { type: "graph"; data: { nodes: { id: string; label: string; status: string }[]; edges: { source: string; target: string }[] } }
  | { type: "quiz_card"; data: { question: string; options: string[]; answer_index: number; explanation?: string | null; knowledge_point?: string | null } }
  | { type: "ls_task_card"; data: { project_id: number; task_index: number; title: string; task_type: string; instructions?: string | null; url: string } }
  | { type: "visualization"; data: VisualizationArtifact };

export function ChatChartCard({ chart }: { chart: ChartData }) {
  if (chart.type === "visualization") return <VisualizationArtifactCard artifact={chart.data} />;
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

  if (chart.type === "quiz_card") {
    return <QuizCard data={chart.data} />;
  }

  if (chart.type === "ls_task_card") {
    return <LsTaskCard data={chart.data} />;
  }

  return null;
}

function RadarCard({ labels, values }: { labels: string[]; values: number[] }) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const chartRef = useRef<{ destroy: () => void } | null>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    let cancelled = false;
    import("chart.js/auto").then(({ default: Chart }) => {
      if (cancelled || ref.current !== canvas) return;
      // React dev mode may run an effect twice while the dynamic import is
      // pending. Destroy both our tracked instance and any orphan attached to
      // this canvas before constructing a replacement.
      chartRef.current?.destroy();
      Chart.getChart(canvas)?.destroy();
      chartRef.current = new Chart(canvas, {
        type: "radar",
        data: {
          labels,
          datasets: [{ data: values, backgroundColor: "rgba(59,130,246,0.2)", borderColor: "#3b82f6" }],
        },
        options: { scales: { r: { min: 0, max: 100 } } },
      });
    });
    return () => {
      cancelled = true;
      chartRef.current?.destroy();
      chartRef.current = null;
    };
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

function LsTaskCard({ data }: { data: { project_id: number; task_index: number; title: string; task_type: string; instructions?: string | null; url: string } }) {
  return (
    <div className="my-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      <div className="mb-1 flex items-center gap-2">
        <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-medium text-blue-500">
          {data.task_type}
        </span>
      </div>
      <div className="mb-2 text-sm font-medium text-[var(--foreground)]">{data.title}</div>
      {data.instructions && (
        <div className="mb-2 text-xs text-[var(--muted-foreground)]">{data.instructions}</div>
      )}
      <a
        href={data.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-block w-full rounded-lg bg-blue-500 px-3 py-1.5 text-center text-xs font-semibold text-white transition-colors hover:bg-blue-600"
      >
        打开标注任务
      </a>
    </div>
  );
}

function QuizCard({ data }: { data: { question: string; options: string[]; answer_index: number; explanation?: string | null; knowledge_point?: string | null } }) {
  const [selected, setSelected] = useState<number | null>(null);
  const answered = selected !== null;
  return (
    <div className="my-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      {data.knowledge_point && (
        <div className="mb-1 text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
          {data.knowledge_point}
        </div>
      )}
      <div className="mb-2 text-sm font-medium text-[var(--foreground)]">{data.question}</div>
      <div className="space-y-1.5">
        {data.options.map((opt, idx) => {
          const isCorrect = idx === data.answer_index;
          const isSelected = idx === selected;
          let style = "border-[var(--border)] text-[var(--foreground)] hover:bg-[var(--muted)]";
          if (answered) {
            if (isCorrect) style = "border-emerald-500/40 bg-emerald-500/10 text-emerald-600";
            else if (isSelected) style = "border-rose-500/40 bg-rose-500/10 text-rose-600";
            else style = "border-[var(--border)] text-[var(--muted-foreground)] opacity-50";
          }
          return (
            <button
              key={idx}
              type="button"
              onClick={() => setSelected(idx)}
              disabled={answered}
              className={`w-full rounded-lg border bg-[var(--card)] px-3 py-1.5 text-left text-xs transition-colors ${style}`}
            >
              <span className="font-semibold">{String.fromCharCode(65 + idx)}.</span> {opt}
              {answered && isCorrect && <span className="ml-1 text-emerald-600">✓</span>}
              {answered && isSelected && !isCorrect && <span className="ml-1 text-rose-600">✗</span>}
            </button>
          );
        })}
      </div>
      {answered && data.explanation && (
        <div className="mt-2 rounded bg-[var(--muted)]/40 px-3 py-2 text-xs text-[var(--muted-foreground)]">
          {data.explanation}
        </div>
      )}
    </div>
  );
}
