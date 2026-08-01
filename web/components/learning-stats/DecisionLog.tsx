"use client";

import { Scale, ArrowRight, Lightbulb } from "lucide-react";
import type { DecisionLog } from "@/lib/learning-stats-api";

const KIND_LABEL: Record<string, string> = {
  task_recommendation: "任务推荐",
  readiness_judgment: "推进判定",
  route_choice: "路线选择",
};

export function DecisionLog({ decisions }: { decisions: DecisionLog[] }) {
  if (!decisions.length) {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="mb-2 flex items-center gap-1.5">
          <Scale className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
          <h3 className="text-sm font-semibold">最近教学决策</h3>
        </div>
        <p className="text-xs text-[var(--muted-foreground)]">
          暂无记录 — Coach 每次推荐任务/判定推进时会记录理由，让你知道"为什么"
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center gap-1.5">
        <Scale className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        <h3 className="text-sm font-semibold">最近教学决策</h3>
        <span className="text-[10px] text-[var(--muted-foreground)]">(可追溯)</span>
      </div>
      <ul className="space-y-2.5">
        {decisions.map((d, i) => (
          <li key={i} className="text-xs">
            <div className="flex items-center gap-1.5 text-[var(--muted-foreground)]">
              <span className="rounded bg-[var(--border)] px-1.5 py-0.5 text-[10px]">
                {KIND_LABEL[d.kind] || d.kind}
              </span>
              <ArrowRight className="h-3 w-3" />
              <span className="font-medium text-[var(--foreground)]">{d.target}</span>
              {d.timestamp ? (
                <span className="ml-auto text-[10px]">{(d.timestamp || "").slice(0, 10)}</span>
              ) : null}
            </div>
            <p className="mt-1 flex items-start gap-1 text-[var(--muted-foreground)]">
              <Lightbulb className="mt-0.5 h-3 w-3 flex-shrink-0" />
              <span>{d.rationale}</span>
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
