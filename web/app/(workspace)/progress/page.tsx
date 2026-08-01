"use client";

import { useEffect, useState } from "react";
import { TrendingUp } from "lucide-react";
import {
  getLearningOverview,
  getRadarDimensions,
  getF1Trend,
  getSkillTree,
  getDecisions,
  getCoursePlan,
  type ProfileOverview,
  type RadarDimension,
  type F1Point,
  type SkillTreeNode,
  type DecisionLog,
  type CoursePlan,
} from "@/lib/learning-stats-api";
import { StatCards } from "@/components/learning-stats/StatCards";
import { RadarChart } from "@/components/learning-stats/RadarChart";
import { F1Curve } from "@/components/learning-stats/F1Curve";
import { SkillTree } from "@/components/learning-stats/SkillTree";
import { DecisionLog as DecisionLogPanel } from "@/components/learning-stats/DecisionLog";

export default function ProgressPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<ProfileOverview | null>(null);
  const [dimensions, setDimensions] = useState<RadarDimension[]>([]);
  const [f1Points, setF1Points] = useState<F1Point[]>([]);
  const [skillTree, setSkillTree] = useState<SkillTreeNode | null>(null);
  const [decisions, setDecisions] = useState<DecisionLog[]>([]);
  const [coursePlan, setCoursePlan] = useState<CoursePlan | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [ov, radar, f1, tree, dec, plan] = await Promise.all([
          getLearningOverview(),
          getRadarDimensions(),
          getF1Trend(),
          getSkillTree(),
          getDecisions(),
          getCoursePlan().catch(() => ({ plan: null as any })),
        ]);
        if (cancelled) return;
        setOverview(ov.overview);
        setDimensions(radar.dimensions);
        setF1Points(f1.points);
        setSkillTree(tree.tree);
        setDecisions(dec.decisions);
        setCoursePlan(plan.plan || null);
      } catch (err: any) {
        if (!cancelled) setError(err.message || "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-20 text-center">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 dark:border-red-800 dark:bg-red-950">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 py-8">
      <div className="flex items-center gap-3">
        <TrendingUp className="h-6 w-6 text-blue-500" />
        <div>
          <h1 className="text-lg font-bold">学习进度</h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            学习数据分析与能力评估
          </p>
        </div>
      </div>

      <StatCards overview={overview} />

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-3 lg:col-span-3">
          <h3 className="text-sm font-semibold">五维能力雷达</h3>
          <RadarChart dimensions={dimensions} />
        </div>
        <div className="space-y-3 lg:col-span-2">
          <SkillTree tree={skillTree} />
        </div>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-semibold">F1 成长曲线</h3>
        <F1Curve points={f1Points} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <DecisionLogPanel decisions={decisions} />
        {coursePlan && (
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="mb-3 text-sm font-semibold">课程计划</h3>
            <ul className="space-y-2">
              {coursePlan.modules.map((m) => (
                <li key={m.name} className="text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{m.name}</span>
                    <span className="text-[10px] text-[var(--muted-foreground)]">{m.target}</span>
                  </div>
                  <div className="mt-0.5 text-[var(--muted-foreground)]">
                    {m.concepts.length ? m.concepts.slice(0, 3).join(" · ") : "—"}
                    {m.concepts.length > 3 ? " …" : ""}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
