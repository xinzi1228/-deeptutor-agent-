export type PerformanceMetricName =
  | "cold_start_interactive"
  | "route_visible"
  | "progress_core_visible"
  | "chat_status_visible"
  | "chat_first_token"
  | "annotation_task_visible"
  | "annotation_mode_switch";

export type PerformanceMetricOutcome = "success" | "error" | "cancelled" | "timeout";

export interface PerformanceMetricInput {
  name: PerformanceMetricName;
  route: string;
  duration_ms: number;
  outcome?: PerformanceMetricOutcome;
  stage?: string;
  tool_calls?: number;
  error_type?: "" | "network" | "timeout" | "cancelled" | "server" | "validation" | "permission" | "unknown";
  build_version?: string;
}

const SAFE_SEGMENT = /^[\w.-]*$/;

export function normalizePerformanceMetric(input: PerformanceMetricInput): Required<PerformanceMetricInput> {
  const route = input.route.split(/[?#]/, 1)[0];
  if (!route.startsWith("/") || route.startsWith("//")) {
    throw new Error("route must be an application path");
  }
  if (!Number.isFinite(input.duration_ms) || input.duration_ms < 0 || input.duration_ms > 600_000) {
    throw new Error("duration_ms is outside the accepted range");
  }
  const stage = input.stage ?? "";
  const buildVersion = input.build_version ?? "";
  if (!SAFE_SEGMENT.test(stage) || !SAFE_SEGMENT.test(buildVersion)) {
    throw new Error("stage and build_version must be identifier-like values");
  }
  return {
    name: input.name,
    route,
    duration_ms: Math.round(input.duration_ms * 100) / 100,
    outcome: input.outcome ?? "success",
    stage,
    tool_calls: Math.max(0, Math.min(100, Math.trunc(input.tool_calls ?? 0))),
    error_type: input.error_type ?? "",
    build_version: buildVersion,
  };
}

export function recordPerformanceMetric(input: PerformanceMetricInput): void {
  let metric: Required<PerformanceMetricInput>;
  try {
    metric = normalizePerformanceMetric(input);
  } catch {
    return;
  }
  void fetch("/api/v1/performance/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    keepalive: true,
    body: JSON.stringify(metric),
  }).catch(() => undefined);
}

export function emitPerformanceMetric(input: PerformanceMetricInput): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent("deeptutor:performance", { detail: input }));
}
