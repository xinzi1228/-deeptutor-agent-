"use client";

import { useEffect, useState } from "react";
import { Clock, Trash2 } from "lucide-react";
import { getCronJobs, deleteCronJob, toggleCronJob, type CronJob } from "@/lib/cron-api";

function describeSchedule(job: CronJob): string {
  const s = job.schedule;
  if (s.kind === "at" && s.at_ms) return `一次 · ${new Date(s.at_ms).toLocaleString()}`;
  if (s.kind === "every" && s.every_seconds) return `每 ${s.every_seconds} 秒`;
  if (s.kind === "cron" && s.expr) return `cron \`${s.expr}\`${s.tz ? ` (${s.tz})` : ""}`;
  return s.kind;
}

function formatNextRun(ms: number | null | undefined): string {
  if (!ms) return "—";
  return new Date(ms).toLocaleString();
}

export default function TasksPage() {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = () => {
    getCronJobs()
      .then((r) => setJobs(r.jobs))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  async function handleToggle(job: CronJob, enabled: boolean) {
    try {
      await toggleCronJob(job.id, enabled);
      load();
    } catch {}
  }

  async function handleDelete(job: CronJob) {
    try {
      await deleteCronJob(job.id);
      load();
    } catch {}
  }

  if (loading) {
    return (
      <div className="h-full overflow-y-auto [scrollbar-gutter:stable]">
        <div className="mx-auto max-w-3xl px-6 py-10 text-sm text-[var(--muted-foreground)]">加载中...</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto [scrollbar-gutter:stable]">
      <div className="mx-auto max-w-3xl space-y-4 px-6 py-8">
        <div className="flex items-center gap-2">
          <Clock className="h-5 w-5 text-blue-500" />
          <div>
            <h1 className="text-lg font-bold">定时任务</h1>
            <p className="text-sm text-[var(--muted-foreground)]">查看和管理学习提醒等定时任务</p>
          </div>
        </div>
        {error && <p className="text-sm text-red-500">加载失败</p>}
        {jobs.length === 0 && (
          <p className="text-sm text-[var(--muted-foreground)]">
            暂无定时任务——和教练说"30 秒后提醒我练标注"即可创建。
          </p>
        )}
        {jobs.map((job) => (
          <div key={job.id} className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold">{job.name || job.id}</span>
              <span className={`rounded px-1.5 py-0.5 text-[10px] ${job.enabled ? "bg-green-500/10 text-green-600" : "bg-[var(--border)] text-[var(--muted-foreground)]"}`}>
                {job.enabled ? "启用中" : "已停用"}
              </span>
              <div className="ml-auto flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleToggle(job, !job.enabled)}
                  className="rounded border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                >
                  {job.enabled ? "停用" : "启用"}
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(job)}
                  aria-label="删除任务"
                  className="rounded border border-[var(--border)] p-1 text-[var(--muted-foreground)] hover:bg-red-500/10 hover:text-red-500"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <div className="mt-2 space-y-1 text-xs text-[var(--muted-foreground)]">
              <p>调度：{describeSchedule(job)}</p>
              <p>下次运行：{formatNextRun(job.next_run_at_ms)}</p>
              {job.last_status && <p>上次：{job.last_status}{job.last_error ? ` · ${job.last_error}` : ""}</p>}
            </div>
            <p className="mt-2 truncate text-xs text-[var(--muted-foreground)]/70">{job.message}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
