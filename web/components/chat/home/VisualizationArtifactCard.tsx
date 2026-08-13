"use client";

import { useEffect, useRef, useState } from "react";
import { Download, Eye, Maximize2, RefreshCw, X } from "lucide-react";
import { Mermaid } from "@/components/Mermaid";
import type { ChartConfiguration } from "chart.js";

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

const CHART_VARIANTS = ["bar", "line", "radar", "doughnut"];

export function VisualizationArtifactCard({ artifact }: { artifact: VisualizationArtifact }) {
  const [details, setDetails] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [variant, setVariant] = useState(0);
  const originalType = String(artifact.content.chart_type || "bar");
  const types = [originalType, ...CHART_VARIANTS.filter((item) => item !== originalType)];
  const activeArtifact = artifact.kind === "chart"
    ? { ...artifact, content: { ...artifact.content, chart_type: types[variant % types.length] } }
    : artifact;
  const body = <ArtifactBody artifact={activeArtifact} />;

  return <div className="my-2 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
    <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
      <div><div className="text-sm font-semibold text-[var(--foreground)]">{artifact.title}</div>{artifact.description && <div className="mt-0.5 text-xs text-[var(--muted-foreground)]">{artifact.description}</div>}</div>
      <div className="flex gap-1">
        {artifact.kind === "chart" && <button type="button" onClick={() => setVariant((value) => value + 1)} className="rounded-lg p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--muted)]" title="保持原始数据，换一种图"><RefreshCw className="h-4 w-4" /></button>}
        <button type="button" onClick={() => setDetails((value) => !value)} className="rounded-lg p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--muted)]" title="查看原始数据与来源"><Eye className="h-4 w-4" /></button>
        <button type="button" onClick={() => setFullscreen(true)} className="rounded-lg p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--muted)]" title="全屏查看"><Maximize2 className="h-4 w-4" /></button>
      </div>
    </div>
    <div className="p-3">{body}</div>
    <div className="flex items-center justify-between border-t border-[var(--border)] px-4 py-2 text-[10px] text-[var(--muted-foreground)]"><span>{artifact.validation_status === "validated" ? "✓ 已校验" : "待校验"} · {artifact.render_protocol.toUpperCase()}</span><span>{artifact.kind === "generated_image" ? "概念示意图" : artifact.unit || "结构图解"}</span></div>
    {details && <ArtifactDetails artifact={activeArtifact} />}
    {fullscreen && <div className="fixed inset-0 z-[100] flex flex-col bg-[var(--background)] p-6"><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">{artifact.title}</h2><button type="button" onClick={() => setFullscreen(false)} className="rounded-lg p-2 hover:bg-[var(--muted)]" aria-label="关闭全屏"><X className="h-5 w-5" /></button></div><div className="min-h-0 flex-1 overflow-auto rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">{body}</div></div>}
  </div>;
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
      const configuration = { type: String(artifact.content.chart_type || "bar"), data: { labels: labels as string[], datasets }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (context: { dataset: { label?: string }; formattedValue: string }) => `${context.dataset.label || "数值"}: ${context.formattedValue} ${artifact.unit}` } } } } } as unknown as ChartConfiguration;
      instance = new Chart(canvas, configuration);
    });
    return () => { cancelled = true; instance?.destroy(); };
  }, [artifact]);
  return <div className="h-72"><canvas ref={ref} aria-label={artifact.alt_text} data-visualization-id={artifact.id} /></div>;
}

function ArtifactDetails({ artifact }: { artifact: VisualizationArtifact }) {
  const downloadJson = () => downloadBlob(new Blob([JSON.stringify(artifact.content, null, 2)], { type: "application/json" }), `${artifact.title}.json`);
  const downloadPng = () => {
    const canvas = document.querySelector<HTMLCanvasElement>(`canvas[data-visualization-id="${CSS.escape(artifact.id)}"]`);
    if (!canvas) return;
    const link = document.createElement("a"); link.href = canvas.toDataURL("image/png"); link.download = `${artifact.title}.png`; link.click();
  };
  return <div className="border-t border-[var(--border)] bg-[var(--muted)]/25 px-4 py-3 text-xs"><dl className="grid gap-2 sm:grid-cols-2"><div><dt className="text-[var(--muted-foreground)]">数据来源</dt><dd className="mt-0.5 break-words">{artifact.source || "概念图解，无数字来源"}</dd></div><div><dt className="text-[var(--muted-foreground)]">更新时间 / 单位</dt><dd className="mt-0.5">{artifact.source_updated_at || "未提供"} · {artifact.unit || "无"}</dd></div><div className="sm:col-span-2"><dt className="text-[var(--muted-foreground)]">校验说明</dt><dd className="mt-0.5">{artifact.validation_message}</dd></div></dl><div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={downloadJson} className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-2.5 py-1.5"><Download className="h-3.5 w-3.5" />下载原始数据</button>{artifact.kind === "chart" && <button type="button" onClick={downloadPng} className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-2.5 py-1.5"><Download className="h-3.5 w-3.5" />下载 PNG</button>}</div></div>;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}
