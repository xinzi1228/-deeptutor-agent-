"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { TrendingUp } from "lucide-react";
import { emitPerformanceMetric } from "@/lib/performance-metrics";
import {
  getLearningOverview,
  getLearningReport,
  getWorkspaceViews,
  getExtensionCatalog,
  getLearningPathDiagram,
  installExtension,
  setExtensionEnabled,
  getRadarDimensions,
  getF1Trend,
  getSkillTree,
  getDecisions,
  getEvaluations,
  getCoursePlan,
  getCoursePlanDocx,
  getTraceLog,
  getTeachingFlow,
  getForesightStats,
  getCoachMetrics,
  reflectMemory,
  getKnowledgeGraph,
  type ProfileOverview,
  type LearningReport,
  type WorkspaceViews,
  type LearningExtension,
  type LearningPathDiagram,
  type RadarDimension,
  type F1Point,
  type SkillTreeNode,
  type DecisionLog,
  type CoursePlan,
  type TeachingEvaluation,
  type ForesightStats,
  type CoachMetrics,
  type KnowledgeGraphData,
  type TraceItem,
  type TeachingFlowState,
} from "@/lib/learning-stats-api";
import { StatCards } from "@/components/learning-stats/StatCards";
import { apiFetch, apiUrl } from "@/lib/api";
import type { VisualizationArtifact } from "@/components/chat/home/VisualizationArtifactCard";

const RadarChart = dynamic(() => import("@/components/learning-stats/RadarChart").then((module) => module.RadarChart), { ssr: false });
const F1Curve = dynamic(() => import("@/components/learning-stats/F1Curve").then((module) => module.F1Curve), { ssr: false });
const SkillTree = dynamic(() => import("@/components/learning-stats/SkillTree").then((module) => module.SkillTree), { ssr: false });
const DecisionLogPanel = dynamic(() => import("@/components/learning-stats/DecisionLog").then((module) => module.DecisionLog));
const EvaluationPanel = dynamic(() => import("@/components/learning-stats/EvaluationPanel").then((module) => module.EvaluationPanel));
const Timeline = dynamic(() => import("@/components/learning-stats/Timeline").then((module) => module.Timeline));
const TeachingFlowPanel = dynamic(() => import("@/components/learning-stats/TeachingFlowPanel").then((module) => module.TeachingFlowPanel));
const CoachMetricsPanel = dynamic(() => import("@/components/learning-stats/CoachMetrics").then((module) => module.CoachMetricsPanel));
const KnowledgeGraphPanel = dynamic(() => import("@/components/learning-stats/KnowledgeGraphPanel").then((module) => module.KnowledgeGraphPanel), { ssr: false });
const CheckinCalendar = dynamic(() => import("@/components/learning-stats/CheckinCalendar").then((module) => module.CheckinCalendar));
const BadgeWall = dynamic(() => import("@/components/learning-stats/BadgeWall").then((module) => module.BadgeWall));
const VisualizationArtifactCard = dynamic(() => import("@/components/chat/home/VisualizationArtifactCard").then((module) => module.VisualizationArtifactCard), { ssr: false });

type Tab = "overview" | "records" | "achievements" | "graph";

const TABS: Array<{ key: Tab; label: string }> = [
  { key: "overview", label: "概览" },
  { key: "records", label: "记录" },
  { key: "achievements", label: "成就" },
  { key: "graph", label: "图谱" },
];

export default function ProgressPage() {
  const loadStartedAt = useRef(0);
  const loadedTabs = useRef(new Set<Tab>(["overview"]));
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<ProfileOverview | null>(null);
  const [learningReport, setLearningReport] = useState<LearningReport | null>(null);
  const [workspaceViews, setWorkspaceViews] = useState<WorkspaceViews | null>(null);
  const [extensions, setExtensions] = useState<LearningExtension[]>([]);
  const [learningPath, setLearningPath] = useState<LearningPathDiagram | null>(null);
  const [dimensions, setDimensions] = useState<RadarDimension[]>([]);
  const [f1Points, setF1Points] = useState<F1Point[]>([]);
  const [skillTree, setSkillTree] = useState<SkillTreeNode | null>(null);
  const [decisions, setDecisions] = useState<DecisionLog[]>([]);
  const [evaluations, setEvaluations] = useState<TeachingEvaluation[]>([]);
  const [coursePlan, setCoursePlan] = useState<CoursePlan | null>(null);
  const [traces, setTraces] = useState<TraceItem[]>([]);
  const [foresight, setForesight] = useState<ForesightStats | null>(null);
  const [coachMetrics, setCoachMetrics] = useState<CoachMetrics | null>(null);
  const [knowledgeGraph, setKnowledgeGraph] = useState<KnowledgeGraphData | null>(null);
  const [teachingFlow, setTeachingFlow] = useState<TeachingFlowState | null>(null);
  const [visualizations, setVisualizations] = useState<VisualizationArtifact[]>([]);

  useEffect(() => {
    loadStartedAt.current = performance.now();
    let cancelled = false;
    async function load() {
      try {
        const [ov, report, workspace, extensionData, radar, f1, tree, fs, artwork] = await Promise.all([
          getLearningOverview(),
          getLearningReport(),
          getWorkspaceViews(),
          getExtensionCatalog(),
          getRadarDimensions(),
          getF1Trend(),
          getSkillTree(),
          getForesightStats(),
          apiFetch(apiUrl("/api/v1/profile/visualizations?limit=6"), { cache: "no-store" }).then((response) => response.ok ? response.json() : { artifacts: [] }),
        ]);
        if (cancelled) return;
        setOverview(ov.overview);
        setLearningReport(report);
        setWorkspaceViews(workspace.views);
        setExtensions(extensionData.extensions);
        setDimensions(radar.dimensions);
        setF1Points(f1.points);
        setSkillTree(tree.tree);
        setForesight(fs);
        setVisualizations(artwork.artifacts || []);
        emitPerformanceMetric({
          name: "progress_core_visible",
          route: "/progress",
          duration_ms: performance.now() - loadStartedAt.current,
          stage: "overview",
        });
        const pathExtension = extensionData.extensions.find((item) => item.id === "learning-path-diagram");
        if (pathExtension?.enabled) {
          getLearningPathDiagram().then((value) => !cancelled && setLearningPath(value.diagram)).catch(() => undefined);
        }
      } catch (err: any) {
        if (!cancelled) setError(err.message || "Failed to load");
        if (!cancelled) emitPerformanceMetric({
          name: "progress_core_visible",
          route: "/progress",
          duration_ms: performance.now() - loadStartedAt.current,
          outcome: "error",
          stage: "overview",
          error_type: "server",
        });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (tab === "overview" || tab === "achievements" || loadedTabs.current.has(tab)) return;
    loadedTabs.current.add(tab);
    if (tab === "records") {
      void Promise.all([
        getDecisions(),
        getCoursePlan().catch(() => ({ plan: null as CoursePlan | null })),
        getTraceLog().catch(() => ({ traces: [] as TraceItem[] })),
        getTeachingFlow().catch(() => null),
      ]).then(([dec, plan, tr, flow]) => {
        setDecisions(dec.decisions);
        setCoursePlan(plan.plan || null);
        setTraces(tr.traces);
        setTeachingFlow(flow);
      }).catch((reason) => setError(reason instanceof Error ? reason.message : "记录加载失败"));
    } else if (tab === "graph") {
      void Promise.all([
        getEvaluations(),
        getCoachMetrics(),
        getKnowledgeGraph().catch(() => null),
      ]).then(([ev, cm, graph]) => {
        setEvaluations(ev.evaluations);
        setCoachMetrics(cm);
        setKnowledgeGraph(graph);
      }).catch((reason) => setError(reason instanceof Error ? reason.message : "图谱加载失败"));
    }
  }, [tab]);

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
    <div className="h-full overflow-y-auto">
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

      <div className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--background)] p-1">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={
              "rounded-md px-3 py-1.5 text-[12px] font-medium transition " +
              (tab === key
                ? "bg-[var(--muted)] text-[var(--foreground)]"
                : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/60")
            }
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <>
          <StatCards overview={overview} foresight={foresight} />

          {learningReport && (
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold">本次学习小结</h2>
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">基于已保存的学习记录生成</p>
                </div>
                <span className="rounded-full bg-[var(--muted)] px-2.5 py-1 text-[11px] text-[var(--muted-foreground)]">
                  {learningReport.summary.data_status === "empty" ? "等待首条记录" : "学习记录已核对"}
                </span>
              </div>
              {learningReport.presentation === "cards" && learningReport.cards.length ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {learningReport.cards.map((card) => (
                    <article key={card.title} className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-3.5">
                      <h3 className="text-xs font-semibold text-[var(--primary)]">{card.title}</h3>
                      <p className="mt-1.5 text-sm leading-6 text-[var(--foreground)]">{card.content}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="space-y-1.5 whitespace-pre-line text-sm leading-6 text-[var(--foreground)]">
                  {learningReport.text}
                </div>
              )}
            </section>
          )}

          {visualizations.length > 0 && <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5"><div className="mb-3"><h2 className="text-sm font-semibold">学习可视化作品</h2><p className="mt-1 text-xs text-[var(--muted-foreground)]">主对话、标注教练和报告共享的已校验作品</p></div><div className="grid gap-4 lg:grid-cols-2">{visualizations.map((artifact) => <VisualizationArtifactCard key={artifact.id} artifact={artifact} />)}</div></section>}

          {workspaceViews && (
            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["待整理问题", workspaceViews.inbox.length, workspaceViews.inbox[0]?.raw_text || "暂无问题"],
                ["已掌握知识点", workspaceViews.mastered.length, workspaceViews.mastered[0]?.knowledge_point || "继续练习后显示"],
                ["确认易错点", workspaceViews.confirmed_errors.length, workspaceViews.confirmed_errors[0] || "暂无确认模式"],
                ["下一任务", workspaceViews.next_tasks.length, workspaceViews.next_tasks[0] || "完成诊断后生成"],
              ].map(([title, count, detail]) => (
                <div key={String(title)} className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <p className="text-xs text-[var(--muted-foreground)]">{title}</p>
                  <p className="mt-1 text-xl font-semibold">{count}</p>
                  <p className="mt-2 line-clamp-2 text-xs text-[var(--muted-foreground)]">{detail}</p>
                </div>
              ))}
            </section>
          )}

          <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
            <div className="mb-3">
              <h2 className="text-sm font-semibold">我的扩展</h2>
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">只提供老师审核过的功能；不会安装外部命令或读取其他同学的数据。</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {extensions.map((extension) => (
                <div key={extension.id} className="rounded-xl border border-[var(--border)] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div><p className="text-sm font-medium">{extension.name}</p><p className="mt-1 text-xs text-[var(--muted-foreground)]">{extension.description}</p></div>
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          if (!extension.installed) await installExtension(extension.id);
                          else await setExtensionEnabled(extension.id, !extension.enabled);
                          const refreshed = await getExtensionCatalog();
                          setExtensions(refreshed.extensions);
                          if (extension.id === "learning-path-diagram") {
                            const next = refreshed.extensions.find((item) => item.id === extension.id);
                            setLearningPath(next?.enabled ? (await getLearningPathDiagram()).diagram : null);
                          }
                        } catch (e: any) { setError(e.message || "扩展操作失败"); }
                      }}
                      className="shrink-0 rounded-md border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--muted)]"
                    >
                      {!extension.installed ? "安装" : extension.enabled ? "停用" : "启用"}
                    </button>
                  </div>
                  <p className="mt-2 text-[11px] text-[var(--muted-foreground)]">权限：{extension.permissions.join("、")}</p>
                </div>
              ))}
            </div>
          </section>

          {learningPath && (
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
              <h2 className="text-sm font-semibold">{learningPath.title}</h2>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {learningPath.nodes.map((node, index) => (
                  <div key={node.id} className="flex items-center gap-2">
                    {index > 0 && <span className="text-[var(--muted-foreground)]">→</span>}
                    <span className="rounded-full border border-[var(--border)] px-3 py-1.5 text-xs">
                      {node.status === "done" ? "✓ " : node.status === "attention" ? "! " : node.status === "goal" ? "★ " : "• "}{node.label}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11px] text-[var(--muted-foreground)]">{learningPath.notice}</p>
            </section>
          )}

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
        </>
      )}

      {tab === "records" && (
        <>
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

          <TeachingFlowPanel flow={teachingFlow} />
          <Timeline traces={traces} />
        </>
      )}

      {tab === "achievements" && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <CheckinCalendar />
          </div>
          <BadgeWall />
        </div>
      )}

      {tab === "graph" && (
        <>
          {knowledgeGraph && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">知识图谱</h3>
              <KnowledgeGraphPanel data={knowledgeGraph} />
            </div>
          )}

          <EvaluationPanel evaluations={evaluations} />

          <CoachMetricsPanel metrics={coachMetrics} />
        </>
      )}
    </div>
    </div>
  );
}
