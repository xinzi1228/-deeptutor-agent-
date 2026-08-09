"use client";

import { useMemo } from "react";

import { AgentStateDot, agentStateLabel } from "@/components/common/AgentStateDot";
import type { StreamEvent } from "@/lib/unified-ws";

export interface ExpertTask {
  expertId: string;
  label: string;
  state: "working" | "done" | "failed" | "waiting";
  status?: string;
  summary?: string;
}

const EXPERT_LABELS: Record<string, string> = {
  learning_planner: "学习规划师",
  task_guide: "任务导引师",
  grading_expert: "评测专家",
  struggle_detective: "卡点侦探",
  report_analyst: "报告分析师",
  session_steward: "会话管家",
};

function summarize(content: string): string {
  const trimmed = content.replace(/^专家\s*\S+\s*结论[：:]\s*/u, "").trim();
  return trimmed.length > 120 ? `${trimmed.slice(0, 120)}…` : trimmed;
}

function expertStateFromEvents(expertId: string, events: StreamEvent[]): ExpertTask {
  const label = EXPERT_LABELS[expertId] ?? expertId;
  const progress = events.filter(
    (e) =>
      e.type === "progress" &&
      e.metadata?.query === expertId &&
      typeof e.content === "string" &&
      e.content.startsWith("专家"),
  );
  const latest = progress[progress.length - 1];
  const done = events.find(
    (e) =>
      e.type === "tool_result" &&
      (e.metadata as any)?.tool_metadata?.delegate?.expert === expertId,
  );
  if (done) {
    return {
      expertId,
      label,
      state: "done",
      status: "分析完成",
      summary: summarize(done.content || ""),
    };
  }
  return {
    expertId,
    label,
    state: "working",
    status: latest?.content,
  };
}

export function ExpertFleetBoard({ events, className = "" }: { events: StreamEvent[]; className?: string }) {
  const tasks = useMemo(() => {
    const calls = events.filter(
      (e) =>
        e.type === "tool_call" &&
        (e.metadata as any)?.tool_name === "delegate_to_expert",
    );
    const uniqueCalls = new Map<string, StreamEvent>();
    calls.forEach((c) => uniqueCalls.set((c.metadata as any)?.args?.expert_id, c));
    return [...uniqueCalls.values()]
      .map((c) => expertStateFromEvents((c.metadata as any)?.args?.expert_id, events))
      .filter((t) => t.expertId);
  }, [events]);

  if (tasks.length === 0) return null;

  return (
    <div className={`space-y-1.5 rounded-xl border border-[var(--border)] bg-[var(--muted)]/30 p-3 ${className}`}>
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--muted-foreground)]">
        <span className="inline-block size-1.5 rounded-full bg-[var(--primary)]" />
        专家协作看板
      </div>
      {tasks.map((task) => (
        <div
          key={task.expertId}
          className="flex items-start gap-2 rounded-lg bg-[var(--background)] px-2.5 py-2"
        >
          <span className="mt-0.5 shrink-0">
            <AgentStateDot state={task.state} size="sm" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-[13px] font-medium text-[var(--foreground)]">
                {task.label}
              </span>
              <span className="shrink-0 text-[11px] text-[var(--muted-foreground)]">
                {agentStateLabel(task.state)}
              </span>
            </div>
            {task.state === "done" ? (
              task.summary && (
                <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-[var(--muted-foreground)]">
                  {task.summary}
                </p>
              )
            ) : (
              task.status && (
                <p className="mt-0.5 text-xs leading-relaxed text-[var(--muted-foreground)]">
                  {task.status}
                </p>
              )
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
