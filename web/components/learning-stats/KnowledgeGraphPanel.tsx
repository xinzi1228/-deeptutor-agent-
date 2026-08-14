"use client";

import { Network, AlertTriangle, CheckCircle2, ArrowDownRight, Unlock } from "lucide-react";
import type { KnowledgeGraphData } from "@/lib/learning-stats-api";

export function KnowledgeGraphPanel({
  data,
  loading = false,
}: {
  data: KnowledgeGraphData | null;
  loading?: boolean;
}) {
  if (loading) {
    return <div aria-label="正在加载知识图谱" className="h-52 animate-pulse rounded-2xl bg-[var(--muted)]/50" />;
  }
  if (!data) return null;
  const graph = data.graph;
  const { mastery, risk_chains } = data;
  const hasGraph = (graph?.nodes ?? 0) > 0;
  const hasData = (mastery.mastered?.length ?? 0) > 0 || (mastery.struggling?.length ?? 0) > 0 || risk_chains.length > 0;

  if (!hasGraph || !hasData) {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="mb-2 flex items-center gap-1.5">
          <Network className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
          <h3 className="text-sm font-semibold">知识图谱 · 技能风险链</h3>
        </div>
        <p className="text-xs text-[var(--muted-foreground)]">
          暂无图谱数据 — 完成诊断与标注练习后，系统会构建技能依赖图谱并标记掌握/风险状态
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center gap-1.5">
        <Network className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        <h3 className="text-sm font-semibold">知识图谱 · 技能风险链</h3>
        <span className="text-[10px] text-[var(--muted-foreground)]">
          {graph?.nodes} 节点 / {graph?.edges} 边
        </span>
      </div>

      {/* 掌握概览 */}
      <div className="mb-3 grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-[var(--border)] p-2">
          <div className="flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]">
            <CheckCircle2 className="h-3 w-3" />
            已掌握
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            {mastery.mastered.length ? (
              mastery.mastered.map((s) => (
                <span key={s.id} className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-500">
                  {s.name}
                </span>
              ))
            ) : (
              <span className="text-[10px] text-[var(--muted-foreground)]">暂无</span>
            )}
          </div>
        </div>
        <div className="rounded-lg border border-[var(--border)] p-2">
          <div className="flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]">
            <AlertTriangle className="h-3 w-3" />
            挣扎中
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            {mastery.struggling.length ? (
              mastery.struggling.map((s) => (
                <span key={s.id} className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-500">
                  {s.name}
                </span>
              ))
            ) : (
              <span className="text-[10px] text-[var(--muted-foreground)]">暂无</span>
            )}
          </div>
        </div>
      </div>

      {/* 风险链列表 */}
      {risk_chains.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-medium text-[var(--muted-foreground)]">风险链（前置未掌握 → 下游受影响）</p>
          {risk_chains.map((chain) => (
            <div key={chain.target} className="rounded-lg border border-[var(--border)] p-2">
              <div className="flex items-center gap-1.5 text-xs">
                <span className="font-semibold text-[var(--foreground)]">{chain.name}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[9px] ${
                    chain.confidence === "high"
                      ? "bg-rose-500/10 text-rose-500"
                      : "bg-[var(--border)] text-[var(--muted-foreground)]"
                  }`}
                >
                  {chain.confidence === "high" ? "有风险" : "低风险"}
                </span>
              </div>
              <div className="mt-1.5 space-y-1 text-[10px]">
                {chain.missing_prereqs.length > 0 && (
                  <div className="flex items-start gap-1 text-[var(--muted-foreground)]">
                    <Unlock className="mt-0.5 h-3 w-3 flex-shrink-0 text-amber-500" />
                    <span>
                      缺失前置:{" "}
                      {chain.missing_prereqs.map((p) => p.name).join("、")}
                    </span>
                  </div>
                )}
                {chain.affected_downstream.length > 0 && (
                  <div className="flex items-start gap-1 text-[var(--muted-foreground)]">
                    <ArrowDownRight className="mt-0.5 h-3 w-3 flex-shrink-0 text-rose-500" />
                    <span>
                      下游受影响:{" "}
                      {chain.affected_downstream.slice(0, 5).map((d) => d.name).join("、")}
                      {chain.affected_downstream.length > 5 ? ` 等 ${chain.affected_downstream.length} 项` : ""}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
