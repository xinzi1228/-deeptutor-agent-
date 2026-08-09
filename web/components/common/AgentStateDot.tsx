"use client";

import { CircleCheck, Loader2, MessageCircleQuestion } from "lucide-react";

export type AgentDotState =
  | "working"
  | "blocked"
  | "waiting"
  | "failed"
  | "done"
  | "idle";

export function agentStateLabel(state: AgentDotState): string {
  switch (state) {
    case "working":
      return "Working";
    case "blocked":
      return "Blocked";
    case "waiting":
      return "Waiting for input";
    case "failed":
      return "Failed";
    case "done":
      return "Done";
    case "idle":
      return "Idle";
  }
}

interface AgentStateDotProps {
  state: AgentDotState;
  size?: "sm" | "md";
  className?: string;
}

/**
 * Shared status-glyph primitive (borrowed from stablyai/orca AgentStateDot).
 * One vocabulary across every surface: working=spin, done=check,
 * waiting=question, blocked/failed=red dot, idle=gray dot.
 */
export function AgentStateDot({
  state,
  size = "sm",
  className = "",
}: AgentStateDotProps) {
  const box = size === "md" ? "h-3 w-3" : "h-2.5 w-2.5";
  const inner = size === "md" ? "size-2" : "size-1.5";
  const icon = size === "md" ? "size-3" : "size-2.5";
  const wrap = `inline-flex shrink-0 items-center justify-center ${box} ${className}`;

  if (state === "working") {
    return (
      <span className={wrap} aria-label={agentStateLabel(state)}>
        <Loader2
          className={`animate-spin text-amber-500 ${icon}`}
          aria-hidden="true"
        />
      </span>
    );
  }

  if (state === "done") {
    return (
      <span className={wrap} aria-label={agentStateLabel(state)}>
        <CircleCheck
          className={`text-emerald-500 ${icon}`}
          aria-hidden="true"
        />
      </span>
    );
  }

  if (state === "waiting") {
    return (
      <span className={wrap} aria-label={agentStateLabel(state)}>
        <MessageCircleQuestion
          className={`text-amber-500 ${icon}`}
          aria-hidden="true"
        />
      </span>
    );
  }

  return (
    <span className={wrap} aria-label={agentStateLabel(state)}>
      <span
        className={`block rounded-full ${inner} ${
          state === "blocked" || state === "failed"
            ? "bg-red-500"
            : "bg-neutral-500/40"
        }`}
      />
    </span>
  );
}
