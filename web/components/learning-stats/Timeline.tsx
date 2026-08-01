"use client";

import { CalendarDays, Target, BookOpen, Stethoscope } from "lucide-react";
import type { Episode } from "@/lib/learning-stats-api";

function kindMeta(kind: string) {
  if (kind === "annotation_exercise")
    return { icon: Target, label: "练习", color: "text-blue-500" };
  if (kind === "theory_mastered")
    return { icon: BookOpen, label: "理论", color: "text-purple-500" };
  return { icon: Stethoscope, label: "诊断", color: "text-green-500" };
}

export function Timeline({ episodes }: { episodes: Episode[] }) {
  if (!episodes.length) {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="mb-2 flex items-center gap-1.5">
          <CalendarDays className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
          <h3 className="text-sm font-semibold">学习时间线</h3>
        </div>
        <p className="text-xs text-[var(--muted-foreground)]">暂无记录</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center gap-1.5">
        <CalendarDays className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        <h3 className="text-sm font-semibold">学习时间线</h3>
      </div>
      <div className="space-y-4">
        {episodes.map((ep) => (
          <div key={ep.date} className="relative border-l border-[var(--border)] pl-4">
            <div className="mb-1.5 flex items-center gap-2">
              <span className="text-xs font-semibold">{ep.date}</span>
              <span className="text-[10px] text-[var(--muted-foreground)]">
                {ep.count} 条记录
              </span>
            </div>
            <ul className="space-y-1.5">
              {ep.records.map((r, i) => {
                const meta = kindMeta(r.type);
                const Icon = meta.icon;
                return (
                  <li key={i} className="flex items-start gap-2 text-xs">
                    <Icon className={`mt-0.5 h-3 w-3 ${meta.color}`} />
                    <div className="min-w-0">
                      <span className="text-[var(--foreground)]">
                        {r.type === "annotation_exercise"
                          ? `${r.task_id} ${r.knowledge_point || ""}`
                          : r.knowledge_point || r.type}
                      </span>
                      {r.type === "annotation_exercise" && typeof r.f1 === "number" && (
                        <span className="ml-1.5 text-[var(--muted-foreground)]">
                          F1={(r.f1 * 100).toFixed(0)}%
                        </span>
                      )}
                      {r.readiness && (
                        <span className="ml-1.5 rounded bg-[var(--border)] px-1 py-0.5 text-[10px] text-[var(--muted-foreground)]">
                          {r.readiness}
                        </span>
                      )}
                      {r.foresight_verified && (
                        <span className={`ml-1.5 text-[10px] ${r.foresight_hit ? "text-green-500" : "text-red-500"}`}>
                          预测{r.foresight_hit ? "命中" : "未中"}
                        </span>
                      )}
                    </div>
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
