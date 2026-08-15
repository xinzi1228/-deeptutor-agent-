"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ClipboardCheck,
  Download,
  FileText,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";

import { apiFetch, apiUrl } from "@/lib/api";

type Run = {
  run_id: string;
  participant_id: string;
  round: "A" | "B";
  task_version: string;
  content_version?: string;
  created_at?: string;
};

type Report = {
  report_version: string;
  draft: boolean;
  draft_mark?: string;
  participants: string[];
  usable_run_count: number;
  total_run_count: number;
  summary: Record<string, unknown>;
  ab_pairs: Array<Record<string, unknown>>;
  per_participant: Record<string, unknown>;
};

/**
 * 真实用户测试与竞赛证据 — admin operations center page.
 *
 * Displays the immutable study runs, the deterministic report summary, draft
 * warnings, and the evidence-package export. The page only reads aggregated
 * numbers and anonymous ids — never recording names, quotes, or recordings.
 */
export default function AdminUsabilityPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [runsRes, reportRes] = await Promise.all([
        apiFetch(apiUrl("/api/v1/usability-study/runs")),
        apiFetch(apiUrl("/api/v1/usability-study/report")),
      ]);
      const runsData = runsRes.ok ? ((await runsRes.json()) as { runs?: Run[] }) : null;
      const reportData = reportRes.ok ? ((await reportRes.json()) as Report) : null;
      setRuns(runsData?.runs ?? []);
      setReport(reportData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "用户测试数据读取失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const exportPackage = async () => {
    const res = await apiFetch(apiUrl("/api/v1/usability-study/export"));
    if (!res.ok) return;
    const blob = new Blob([JSON.stringify(await res.json(), null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "标注星图-竞赛证据包.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  const summary = report?.summary ?? {};
  const participantCount = Number(summary.participant_count ?? 0);

  return (
    <div className="min-h-full bg-[var(--background)] px-6 py-8 [scrollbar-gutter:stable]">
      <div className="mx-auto max-w-5xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-600">
              <ShieldCheck className="h-3.5 w-3.5" />
              真实用户测试 · 竞赛证据
            </div>
            <h1 className="font-serif text-3xl font-semibold tracking-tight">
              用户测试与证据包
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted-foreground)]">
              仅保存匿名参与者（S01 / S02 / T01）与不可变运行记录；报告从真实事件
              确定性生成，不补填缺失记录。
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void exportPackage()}
              className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border)] px-3 py-2 text-xs"
            >
              <Download className="h-4 w-4" />
              导出证据包
            </button>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--foreground)] px-3 py-2 text-xs text-[var(--background)]"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              刷新
            </button>
          </div>
        </header>

        {error && (
          <div className="mt-6 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-600">
            {error}
          </div>
        )}

        {report?.draft && (
          <div className="mt-6 flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-600">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{report.draft_mark || "报告为草稿，不可用于正式提交。"}</span>
          </div>
        )}

        {!report && loading ? (
          <div className="mt-7 grid gap-4 md:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-32 animate-pulse rounded-2xl bg-[var(--muted)]" />
            ))}
          </div>
        ) : (
          <section className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="参与者" value={String(participantCount)} icon={<Users className="h-4 w-4" />} />
            <MetricCard label="可用运行" value={`${report?.usable_run_count ?? 0}/${report?.total_run_count ?? 0}`} icon={<ClipboardCheck />} />
            <MetricCard label="配对 A/B" value={String(report?.ab_pairs?.length ?? 0)} icon={<FileText />} />
            <MetricCard label="报告版本" value={report?.report_version ?? "—"} icon={<FileText />} />
          </section>
        )}

        <section className="mt-7">
          <h2 className="text-sm font-semibold text-[var(--muted-foreground)]">
            测试运行记录（不可变）
          </h2>
          <div className="mt-3 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
            {runs.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-[var(--muted-foreground)]">
                暂无测试运行记录。
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                    <th className="px-5 py-3 font-medium">运行</th>
                    <th className="px-5 py-3 font-medium">参与者</th>
                    <th className="px-5 py-3 font-medium">轮次</th>
                    <th className="px-5 py-3 font-medium">任务版本</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {runs.map((run) => (
                    <tr key={run.run_id} className="hover:bg-[var(--background)]/40">
                      <td className="px-5 py-3 font-mono text-xs text-[var(--foreground)]">
                        {run.run_id}
                      </td>
                      <td className="px-5 py-3">{run.participant_id}</td>
                      <td className="px-5 py-3">
                        <span className={`rounded-full px-2 py-0.5 text-xs ${
                          run.round === "A" ? "bg-amber-500/10 text-amber-600" : "bg-emerald-500/10 text-emerald-600"
                        }`}>
                          {run.round === "A" ? "优化前" : "优化后"}
                        </span>
                      </td>
                      <td className="px-5 py-3 font-mono text-xs text-[var(--muted-foreground)]">
                        {run.task_version}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <p className="mt-8 text-center text-xs text-[var(--muted-foreground)]">
          报告不声明统计显著性；所有提升百分比均保留原始分子分母。
        </p>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex h-24 flex-col justify-between rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
      <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
        <span className="rounded-lg bg-[var(--muted)] p-1.5">{icon}</span>
        {label}
      </div>
      <span className="text-xl font-semibold tabular-nums text-[var(--foreground)]">
        {value}
      </span>
    </div>
  );
}
