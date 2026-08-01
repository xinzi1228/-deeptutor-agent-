"use client";

import { Target, BarChart3, BookOpen, Flag, Eye } from "lucide-react";
import type { ProfileOverview, ForesightStats } from "@/lib/learning-stats-api";

interface StatCardsProps {
  overview: ProfileOverview | null;
  foresight?: ForesightStats | null;
}

export function StatCards({ overview, foresight }: StatCardsProps) {
  if (!overview) return null;

  const cards = [
    {
      icon: Target,
      label: "最新 F1",
      value: overview.latest_f1 != null ? `${Math.round(overview.latest_f1 * 100)}%` : "—",
      sub: `P:${overview.latest_precision != null ? Math.round(overview.latest_precision * 100) : "—"}% R:${overview.latest_recall != null ? Math.round(overview.latest_recall * 100) : "—"}%`,
    },
    {
      icon: BarChart3,
      label: "练习进度",
      value: `${overview.tasks_passed}/${overview.total_tasks_completed}`,
      sub: `通过率 ${Math.round(overview.pass_rate * 100)}%`,
    },
    {
      icon: BookOpen,
      label: "理论掌握",
      value: `${overview.total_theory_mastered}`,
      sub: "个知识点",
    },
    {
      icon: Flag,
      label: overview.teaching_mode || "教学模式",
      value: overview.goal_type || "—",
      sub: overview.mission
        ? overview.mission.length > 12
          ? overview.mission.slice(0, 12) + "..."
          : overview.mission
        : "",
    },
  ];

  if (foresight && (foresight.total > 0 || foresight.verified > 0)) {
    cards.push({
      icon: Eye,
      label: "预测命中率",
      value: foresight.hit_rate != null ? `${Math.round(foresight.hit_rate * 100)}%` : "—",
      sub: `${foresight.hits}/${foresight.verified} 已验证, ${foresight.open} 待验证`,
    });
  }

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4"
        >
          <div className="mb-1 flex items-center gap-1.5 text-[var(--muted-foreground)]">
            <card.icon className="h-3.5 w-3.5" />
            <span className="text-xs">{card.label}</span>
          </div>
          <div className="text-xl font-bold">{card.value}</div>
          <div className="mt-0.5 text-xs text-[var(--muted-foreground)]">{card.sub}</div>
        </div>
      ))}
    </div>
  );
}
