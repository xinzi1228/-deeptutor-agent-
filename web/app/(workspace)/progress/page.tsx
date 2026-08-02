"use client";

import { useEffect, useState } from "react";
import { TrendingUp } from "lucide-react";
import {
  getLearningOverview,
  getRadarDimensions,
  getF1Trend,
  getSkillTree,
  getDecisions,
  getEvaluations,
  getCoursePlan,
  getCoursePlanDocx,
  getEpisodes,
  getForesightStats,
  getCoachMetrics,
  reflectMemory,
  getKnowledgeGraph,
  type ProfileOverview,
  type RadarDimension,
  type F1Point,
  type SkillTreeNode,
  type DecisionLog,
  type CoursePlan,
  type TeachingEvaluation,
  type Episode,
  type ForesightStats,
  type CoachMetrics,
  type KnowledgeGraphData,
} from "@/lib/learning-stats-api";
import { StatCards } from "@/components/learning-stats/StatCards";
import { RadarChart } from "@/components/learning-stats/RadarChart";
import { F1Curve } from "@/components/learning-stats/F1Curve";
import { SkillTree } from "@/components/learning-stats/SkillTree";
import { DecisionLog as DecisionLogPanel } from "@/components/learning-stats/DecisionLog";
import { EvaluationPanel } from "@/components/learning-stats/EvaluationPanel";
import { Timeline } from "@/components/learning-stats/Timeline";
import { CoachMetricsPanel } from "@/components/learning-stats/CoachMetrics";
import { KnowledgeGraphPanel } from "@/components/learning-stats/KnowledgeGraphPanel";
import { CheckinCalendar } from "@/components/learning-stats/CheckinCalendar";
import { BadgeWall } from "@/components/learning-stats/BadgeWall";

export default function ProgressPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<ProfileOverview | null>(null);
  const [dimensions, setDimensions] = useState<RadarDimension[]>([]);
  const [f1Points, setF1Points] = useState<F1Point[]>([]);
  const [skillTree, setSkillTree] = useState<SkillTreeNode | null>(null);
  const [decisions, setDecisions] = useState<DecisionLog[]>([]);
  const [evaluations, setEvaluations] = useState<TeachingEvaluation[]>([]);
  const [coursePlan, setCoursePlan] = useState<CoursePlan | null>(null);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [foresight, setForesight] = useState<ForesightStats | null>(null);
  const [coachMetrics, setCoachMetrics] = useState<CoachMetrics | null>(null);
  const [knowledgeGraph, setKnowledgeGraph] = useState<KnowledgeGraphData | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [ov, radar, f1, tree, dec, ev, plan, ep, fs, cm, kg] = await Promise.all([
          getLearningOverview(),
          getRadarDimensions(),
          getF1Trend(),
          getSkillTree(),
          getDecisions(),
          getEvaluations(),
          getCoursePlan().catch(() => ({ plan: null as any })),
          getEpisodes(),
          getForesightStats(),
          getCoachMetrics(),
          getKnowledgeGraph().catch(() => null),
        ]);
        if (cancelled) return;
        setOverview(ov.overview);
        setDimensions(radar.dimensions);
        setF1Points(f1.points);
        setSkillTree(tree.tree);
        setDecisions(dec.decisions);
        setEvaluations(ev.evaluations);
        setCoursePlan(plan.plan || null);
        setEpisodes(ep.episodes);
        setForesight(fs);
        setCoachMetrics(cm);
        setKnowledgeGraph(kg);
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
        <button
          onClick={async () => {
            try {
              await reflectMemory();
              window.location.reload();
            } catch (e: any) {
              setError(e.message || "记忆整理失败");
            }
          }}
          className="ml-auto rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs text-[var(--muted-foreground)] transition-colors hover:bg-[var(--border)]"
        >
          记忆整理
        </button>
      </div>

      <StatCards overview={overview} foresight={foresight} />

      <CoachMetricsPanel metrics={coachMetrics} />

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

      {knowledgeGraph && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">知识图谱</h3>
          <KnowledgeGraphPanel data={knowledgeGraph} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <CheckinCalendar />
        </div>
        <BadgeWall />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <DecisionLogPanel decisions={decisions} />
        {coursePlan && (
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold">课程计划</h3>
              <button
                onClick={async () => {
                  try {
                    const d = await getCoursePlanDocx();
                    if (d.docx.url) window.open(d.docx.url, "_blank");
                  } catch {}
                }}
                className="rounded border border-[var(--border)] px-2 py-0.5 text-[10px] text-[var(--muted-foreground)] transition-colors hover:bg-[var(--border)]"
              >
                下载手册
              </button>
            </div>
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

      <EvaluationPanel evaluations={evaluations} />

      <Timeline episodes={episodes} />
    </div>
  );
}
