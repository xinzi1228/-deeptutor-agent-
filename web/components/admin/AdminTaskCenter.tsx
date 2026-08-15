"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileSearch,
  Inbox,
  RefreshCw,
} from "lucide-react";

import { apiFetch, apiUrl } from "@/lib/api";

type RevisionStatus = "candidate" | "changes_requested" | "rejected" | "published";
type JobStatus =
  | "queued"
  | "running"
  | "needs_review"
  | "completed"
  | "failed"
  | "cancelled";

interface PendingRevision {
  revision_id: string;
  status: RevisionStatus;
  summary?: string;
  content_ref?: string;
  created_at?: string;
}

interface TextbookJob {
  id: string;
  status: JobStatus;
  original_name?: string;
  progress_message?: string;
  error?: string;
  created_at?: string;
}

interface TaskCenterState {
  pendingRevisions: PendingRevision[];
  failedJobs: TextbookJob[];
  needsReviewJobs: TextbookJob[];
  loading: boolean;
  error: string;
}

/**
 * 统一任务中心 — aggregates the long-running / review queues that an admin
 * homepage should surface first: content-governance revisions awaiting human
 * review, and textbook-ingestion jobs that failed or need review. Items link
 * into the owning admin center. No conversation text or annotation content is
 * ever read here — only statuses and counts.
 */
export default function AdminTaskCenter() {
  const [state, setState] = useState<TaskCenterState>({
    pendingRevisions: [],
    failedJobs: [],
    needsReviewJobs: [],
    loading: true,
    error: "",
  });

  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const [revisions, jobs] = await Promise.all([
        apiFetch(
          apiUrl("/api/v1/content-governance/revisions?status=candidate"),
        ).then(async (res) =>
          res.ok ? ((await res.json()) as { revisions: PendingRevision[] }) : null,
        ),
        apiFetch(apiUrl("/api/v1/textbooks/jobs?limit=200")).then(async (res) =>
          res.ok ? ((await res.json()) as { jobs: TextbookJob[] }) : null,
        ),
      ]);
      const pending =
        revisions?.revisions.filter(
          (r) => r.status === "candidate" || r.status === "changes_requested",
        ) ?? [];
      const jobsList = jobs?.jobs ?? [];
      setState({
        pendingRevisions: pending,
        failedJobs: jobsList.filter((job) => job.status === "failed"),
        needsReviewJobs: jobsList.filter((job) => job.status === "needs_review"),
        loading: false,
        error: "",
      });
    } catch {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: "任务中心读取失败",
      }));
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const total =
    state.pendingRevisions.length +
    state.failedJobs.length +
    state.needsReviewJobs.length;

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="rounded-xl bg-amber-500/10 p-2 text-amber-600">
            <Inbox className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-base font-semibold">统一任务中心</h2>
            <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
              待审核、失败与需复核任务；长任务可在对应中心重试。
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!state.loading && total > 0 && (
            <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-600">
              {total} 项待处理
            </span>
          )}
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-2.5 py-1.5 text-xs text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${state.loading ? "animate-spin" : ""}`} />
            刷新
          </button>
        </div>
      </div>

      {state.error && (
        <p className="mt-4 rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-600">
          {state.error}
        </p>
      )}

      {state.loading ? (
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-[var(--muted)]" />
          ))}
        </div>
      ) : total === 0 ? (
        <div className="mt-5 flex items-center gap-2 rounded-xl bg-emerald-500/5 px-4 py-3 text-xs text-emerald-600">
          <CheckCircle2 className="h-4 w-4" />
          当前没有待审核、失败或需复核的任务。
        </div>
      ) : (
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <QueueCard
            title="待人工审核"
            count={state.pendingRevisions.length}
            icon={<FileSearch className="h-4 w-4" />}
            tone="amber"
            href="/admin/content"
            items={state.pendingRevisions.map((r) => ({
              id: r.revision_id,
              label: r.summary || r.content_ref || r.revision_id,
            }))}
          />
          <QueueCard
            title="导入失败"
            count={state.failedJobs.length}
            icon={<AlertTriangle className="h-4 w-4" />}
            tone="rose"
            href="/admin/content"
            items={state.failedJobs.map((job) => ({
              id: job.id,
              label: job.original_name || job.id,
              detail: job.error || job.progress_message,
            }))}
          />
          <QueueCard
            title="需人工复核"
            count={state.needsReviewJobs.length}
            icon={<Clock3 className="h-4 w-4" />}
            tone="sky"
            href="/admin/content"
            items={state.needsReviewJobs.map((job) => ({
              id: job.id,
              label: job.original_name || job.id,
              detail: job.progress_message,
            }))}
          />
        </div>
      )}
    </section>
  );
}

function QueueCard({
  title,
  count,
  icon,
  tone,
  href,
  items,
}: {
  title: string;
  count: number;
  icon: React.ReactNode;
  tone: "amber" | "rose" | "sky";
  href: string;
  items: { id: string; label: string; detail?: string }[];
}) {
  const tones: Record<string, string> = {
    amber: "bg-amber-500/10 text-amber-600",
    rose: "bg-rose-500/10 text-rose-600",
    sky: "bg-sky-500/10 text-sky-600",
  };
  return (
    <div className="flex flex-col rounded-xl border border-[var(--border)] bg-[var(--background)]/40 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>
          {icon}
          {title}
        </span>
        <span className="text-lg font-semibold tabular-nums text-[var(--foreground)]">
          {count}
        </span>
      </div>
      <ul className="mt-3 flex-1 space-y-1.5">
        {items.slice(0, 4).map((item) => (
          <li key={item.id} className="truncate text-xs text-[var(--muted-foreground)]" title={item.detail || item.label}>
            {item.label}
          </li>
        ))}
        {items.length === 0 && (
          <li className="text-xs text-[var(--muted-foreground)]">无</li>
        )}
      </ul>
      <Link
        href={href}
        className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-[var(--primary)]"
      >
        {count > 0 ? "前往处理" : "查看"}
        <span aria-hidden>→</span>
      </Link>
    </div>
  );
}
