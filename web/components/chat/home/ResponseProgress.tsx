"use client";

import { CheckCircle2, CircleAlert, Loader2 } from "lucide-react";
import { useMemo } from "react";

import { buildResponseProgress } from "@/lib/response-progress";
import type { StreamEvent } from "@/lib/unified-ws";

export function ResponseProgress({
  events,
  isStreaming,
}: {
  events: StreamEvent[];
  isStreaming: boolean;
}) {
  const progress = useMemo(
    () => buildResponseProgress(events, isStreaming),
    [events, isStreaming],
  );
  if (!progress.visible || (progress.status === "completed" && !isStreaming)) {
    return null;
  }

  const isDone = progress.status === "completed";
  const isProblem = ["failed", "cancelled", "degraded"].includes(progress.status);
  const Icon = isDone ? CheckCircle2 : isProblem ? CircleAlert : Loader2;
  const tone = isDone
    ? "text-emerald-600 dark:text-emerald-400"
    : isProblem
      ? "text-amber-600 dark:text-amber-400"
      : "text-[var(--primary)]";

  return (
    <div
      className="mb-2 flex items-center gap-2 rounded-lg border border-[var(--border)]/70 bg-[var(--muted)]/25 px-3 py-2 text-xs"
      aria-live="polite"
      data-response-status={progress.status}
    >
      <Icon
        size={14}
        className={`${tone} shrink-0 ${progress.status === "running" ? "animate-spin" : ""}`}
      />
      <span className="min-w-0 flex-1 truncate text-[var(--foreground)]">
        {progress.label}
      </span>
      <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">
        {progress.completedSteps}/{progress.totalSteps}
      </span>
    </div>
  );
}
