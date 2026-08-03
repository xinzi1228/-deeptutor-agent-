"use client";

import { useState } from "react";
import { CalendarDays, Target, BookOpen, Stethoscope, ChevronDown } from "lucide-react";
import type { TraceItem } from "@/lib/learning-stats-api";

function kindMeta(kind: string) {
  if (kind === "annotation_exercise")
    return { icon: Target, label: "练习", color: "text-blue-500" };
  if (kind === "theory_mastered")
    return { icon: BookOpen, label: "理论", color: "text-purple-500" };
  return { icon: Stethoscope, label: "诊断", color: "text-green-500" };
}

function traceKey(t: TraceItem, i: number) {
  return `${t.timestamp ?? t.type}-${i}`;
}

export function Timeline({ traces }: { traces: TraceItem[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggle(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  if (!traces.length) {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="mb-2 flex items-center gap-1.5">
          <CalendarDays className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
          <h3 className="text-sm font-semibold">教学轨迹</h3>
        </div>
        <p className="text-xs text-[var(--muted-foreground)]">暂无记录</p>
      </div>
    );
  }

  const byDate = new Map<string, TraceItem[]>();
  for (const t of traces) {
    const d = t.date ?? (t.timestamp ? t.timestamp.slice(0, 10) : "未知日期");
    const list = byDate.get(d) ?? [];
    list.push(t);
    byDate.set(d, list);
  }

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center gap-1.5">
        <CalendarDays className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        <h3 className="text-sm font-semibold">教学轨迹</h3>
      </div>
      <div className="space-y-4">
        {[...byDate.entries()].map(([date, items]) => (
          <div key={date} className="relative border-l border-[var(--border)] pl-4">
            <div className="mb-1.5 flex items-center gap-2">
              <span className="text-xs font-semibold">{date}</span>
              <span className="text-[10px] text-[var(--muted-foreground)]">
                {items.length} 条记录
              </span>
            </div>
            <ul className="space-y-1.5">
              {items.map((t, i) => {
                const meta = kindMeta(t.type);
                const Icon = meta.icon;
                const isExercise = t.type === "annotation_exercise";
                const key = traceKey(t, i);
                const isOpen = expanded.has(key);
                return (
                  <li key={key} className="text-xs">
                    {isExercise ? (
                      <button
                        type="button"
                        onClick={() => toggle(key)}
                        className="flex w-full items-start gap-2 text-left"
                      >
                        <Icon className={`mt-0.5 h-3 w-3 shrink-0 ${meta.color}`} />
                        <span className="min-w-0 flex-1">
                          <span className="text-[var(--foreground)]">
                            {t.task_id} {t.knowledge_point || ""}
                          </span>
                          {typeof t.f1 === "number" && (
                            <span className="ml-1.5 text-[var(--muted-foreground)]">
                              F1={(t.f1 * 100).toFixed(0)}%
                            </span>
                          )}
                          {t.readiness && (
                            <span className="ml-1.5 rounded bg-[var(--border)] px-1 py-0.5 text-[10px] text-[var(--muted-foreground)]">
                              {t.readiness}
                            </span>
                          )}
                        </span>
                        <span className="flex shrink-0 items-center gap-1 text-[10px] text-[var(--muted-foreground)]">
                          {isOpen ? "收起" : "展开"}
                          <ChevronDown
                            className={`h-3 w-3 transition-transform ${isOpen ? "rotate-180" : ""}`}
                          />
                        </span>
                      </button>
                    ) : (
                      <div className="flex items-start gap-2">
                        <Icon className={`mt-0.5 h-3 w-3 ${meta.color}`} />
                        <span className="text-[var(--foreground)]">
                          {t.knowledge_point || t.type}
                        </span>
                      </div>
                    )}
                    {isOpen && (
                      <div className="ml-5 mt-1.5 space-y-1.5">
                        {t.knowledge_points?.length ? (
                          <div className="text-[10px] text-[var(--muted-foreground)]">
                            {t.knowledge_points.join(" · ")}
                          </div>
                        ) : null}
                        {t.intervention && (
                          <div className="rounded bg-red-500/10 px-2 py-1 text-[10px] text-red-500">
                            卡住介入: {t.intervention.rationale}
                          </div>
                        )}
                        {t.decision && (
                          <div className="rounded bg-blue-500/10 px-2 py-1 text-[10px] text-blue-500">
                            推进决策 ({t.decision.kind}): {t.decision.rationale}
                          </div>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
