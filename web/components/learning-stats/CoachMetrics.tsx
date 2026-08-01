"use client";

import { Gauge, TrendingUp, Eye, CheckCircle2, History, Scale, Target } from "lucide-react";
import type { CoachMetrics } from "@/lib/learning-stats-api";

function pct(v: number | null): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

function growth(v: number | null): string {
  if (v == null) return "—";
  const s = Math.round(v * 100);
  return `${s > 0 ? "+" : ""}${s}%`;
}

export function CoachMetricsPanel({ metrics }: { metrics: CoachMetrics | null }) {
  if (!metrics) return null;

  const rows = [
    { icon: Target, label: "F1 提升率", value: growth(metrics.f1_growth), hint: "相对首个练习" },
    { icon: TrendingUp, label: "最新 F1", value: metrics.latest_f1 != null ? `${Math.round(metrics.latest_f1 * 100)}%` : "—", hint: `${metrics.tasks_completed} 个任务` },
    { icon: CheckCircle2, label: "模式确认率", value: pct(metrics.pattern_confirmation_rate), hint: "证据充分的错误模式" },
    { icon: Eye, label: "预测命中率", value: pct(metrics.foresight_hit_rate), hint: "Coach 预测的准确性" },
    { icon: History, label: "教学自改进", value: `${metrics.teaching_improvements}`, hint: "流程版本优化次数" },
    { icon: Scale, label: "决策审计", value: `${metrics.decision_audit_entries}`, hint: "推荐理由已记录" },
  ];

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center gap-1.5">
        <Gauge className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        <h3 className="text-sm font-semibold">教练绩效</h3>
        <span className="text-[10px] text-[var(--muted-foreground)]">(可衡量)</span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {rows.map((r) => (
          <div key={r.label} className="rounded-lg border border-[var(--border)] p-2">
            <div className="flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]">
              <r.icon className="h-3 w-3" />
              {r.label}
            </div>
            <div className="mt-0.5 text-lg font-bold">{r.value}</div>
            <div className="text-[10px] text-[var(--muted-foreground)]">{r.hint}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
