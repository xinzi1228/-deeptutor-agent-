"use client";

import { GitBranch } from "lucide-react";
import type { TeachingFlowState } from "@/lib/learning-stats-api";

const STEP_ORDER = ["select_task", "show_task", "waiting", "evaluate", "feedback", "record"];

const STEP_LABELS: Record<string, string> = {
  select_task: "选任务", show_task: "展示任务", waiting: "等待提交",
  evaluate: "评测", feedback: "反馈", record: "记录",
};

const STEP_STATUS_STYLE: Record<string, string> = {
  done: "bg-green-500 text-white",
  in_progress: "bg-blue-500 text-white ring-2 ring-blue-300",
  blocked: "bg-red-500 text-white",
  pending: "bg-[var(--border)] text-[var(--muted-foreground)]",
};

export function TeachingFlowPanel({ flow }: { flow: TeachingFlowState | null }) {
  if (!flow || !flow.has_flow) {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="mb-1 flex items-center gap-1.5">
          <GitBranch className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
          <h3 className="text-sm font-semibold">教学流程</h3>
        </div>
        <p className="text-xs text-[var(--muted-foreground)]">
          暂无进行中的任务——和教练开始练习后，这里会显示 6 步教学进度。
        </p>
      </div>
    );
  }

  const steps = flow.steps ?? {};
  const blocked = flow.blocked;

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center gap-1.5">
        <GitBranch className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        <h3 className="text-sm font-semibold">教学流程</h3>
        <span className="ml-auto text-xs text-[var(--muted-foreground)]">
          {flow.task_id ? `任务 ${flow.task_id}` : "进行中"}
          {flow.expert ? ` · 专家: ${flow.expert}` : ""}
        </span>
      </div>
      <div className="flex items-center gap-1">
        {STEP_ORDER.map((step, idx) => {
          const meta = steps[step] ?? {};
          const style = STEP_STATUS_STYLE[meta.status ?? "pending"] ?? STEP_STATUS_STYLE.pending;
          return (
            <div key={step} className="flex flex-1 items-center gap-1">
              <div className="flex flex-1 flex-col items-center gap-1">
                <div className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold ${style}`}>
                  {idx + 1}
                </div>
                <span className="text-[10px] text-[var(--muted-foreground)]">{STEP_LABELS[step]}</span>
              </div>
              {idx < STEP_ORDER.length - 1 && (
                <div className={`h-px flex-1 ${meta.status === "done" ? "bg-green-500/60" : "bg-[var(--border)]"}`} />
              )}
            </div>
          );
        })}
      </div>
      {blocked && (
        <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-[var(--muted-foreground)]">
          <span className="font-semibold text-red-500">阻塞</span>：{blocked.reason}
          <span className="ml-2">建议：{blocked.next_action}</span>
        </div>
      )}
    </div>
  );
}
