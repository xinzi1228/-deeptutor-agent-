"use client";

import { useEffect, useRef, useState } from "react";
import { Download, Eye, Maximize2, X } from "lucide-react";
import { Mermaid } from "@/components/Mermaid";

export type VisualizationArtifact = {
  id: string;
  kind: "chart" | "diagram" | "generated_image";
  title: string;
  description: string;
  alt_text: string;
  render_protocol: "chartjs" | "mermaid" | "image";
  content: Record<string, unknown>;
  source: string;
  unit: string;
  source_updated_at: string;
  validation_status: string;
  validation_message: string;
  created_at: string;
};

export function VisualizationArtifactCard({ artifact }: { artifact: VisualizationArtifact }) {
  const [details, setDetails] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const body = <ArtifactBody artifact={artifact} />;
  return (
    <div className="my-2 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
      <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-[var(--foreground)]">{artifact.title}</div>
          {artifact.description && <div className="mt-0.5 text-xs text-[var(--muted-foreground)]">{artifact.description}</div>}
        </div>
        <div className="flex gap-1">
          <button type="button" onClick={() => setDetails((value) => !value)} className="rounded-lg p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--muted)]" title="查看原始数据与来源"><Eye className="h-4 w-4" /></button>
          <button type="button" onClick={() => setFullscreen(true)} className="rounded-lg p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--muted)]" title="全屏查看"><Maximize2 className="h-4 w-4" /></button>
        </div>
      </div>
      <div className="p-3">{body}</div>
      <div className="flex items-center justify-between border-t border-[var(--border)] px-4 py-2 text-[10px] text-[var(--muted-foreground)]">
        <span>{artifact.validation_status === "validated" ? "✓ 已校验" : "待校验"} · {artifact.render_protocol.toUpperCase()}</span>
        <span>{artifact.kind === "generated_image" ? "概念示意图" : artifact.unit || "结构图解"}</span>
      </div>
      {details && <ArtifactDetails artifact={artifact} />}
      {fullscreen && <div className="fixed inset-0 z-[100] flex flex-col bg-[var(--background)] p-6"><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">{artifact.title}</h2><button type="button" onClick={() => setFullscreen(false)} className="rounded-lg p-2 hover:bg-[var(--muted)]"><X className="h-5 w-5" /></button></div><div className="min-h-0 flex-1 overflow-auto rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">{body}</div></div>}
    </div>
  );
}

function ArtifactBody({ artifact }: { artifact: VisualizationArtifact }) {
  if (artifact.render_protocol === "mermaid") return <Mermaid chart={String(artifact.content.mermaid || "")} />;
  if (artifact.render_protocol === "image") return <img src={String(artifact.content.image_url || "")} alt={artifact.alt_text} className="mx-auto max-h-[420px] rounded-xl object-contain" />;
  return <GenericChart artifact={artifact} />;
}

function GenericChart({ artifact }: { artifact: VisualizationArtifact }) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    let cancelled = false;
    let instance: { destroy: () => void } | null = null;
    import("chart.js/auto").then(({ default: Chart }) => {
      if (cancelled || ref.current !== canvas) return;
      Chart.getChart(canvas)?.destroy();
      const labels = Array.isArray(artifact.content.labels) ? artifact.content.labels : [];
      const datasets = Array.isArray(artifact.content.datasets) ? artifact.content.datasets : [];
      instance = new Chart(canvas, {
        type: String(artifact.content.chart_type || "bar") as any,
        data: { labels: labels as string[], datasets: datasets as any[] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (context: { dataset: { label?: string }; formattedValue: string }) => `${context.dataset.label || "数值"}: ${context.formattedValue} ${artifact.unit}` } } } },
      });
    });
    return () => { cancelled = true; instance?.destroy(); };
  }, [artifact]);
  return <div className="h-72"><canvas ref={ref} aria-label={artifact.alt_text} /></div>;
}

function ArtifactDetails({ artifact }: { artifact: VisualizationArtifact }) {
  const download = () => {
    const blob = new Blob([JSON.stringify(artifact.content, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `${artifact.title}.json`; link.click(); URL.revokeObjectURL(url);
  };
  return <div className="border-t border-[var(--border)] bg-[var(--muted)]/25 px-4 py-3 text-xs"><dl className="grid gap-2 sm:grid-cols-2"><div><dt className="text-[var(--muted-foreground)]">数据来源</dt><dd className="mt-0.5 break-words">{artifact.source || "概念图解，无数字来源"}</dd></div><div><dt className="text-[var(--muted-foreground)]">更新时间 / 单位</dt><dd className="mt-0.5">{artifact.source_updated_at || "未提供"} · {artifact.unit || "无"}</dd></div><div className="sm:col-span-2"><dt className="text-[var(--muted-foreground)]">校验说明</dt><dd className="mt-0.5">{artifact.validation_message}</dd></div></dl><button type="button" onClick={download} className="mt-3 inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-2.5 py-1.5"><Download className="h-3.5 w-3.5" />下载原始数据</button></div>;
}
