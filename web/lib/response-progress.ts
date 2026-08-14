export type ResponseProgressStatus =
  | "idle"
  | "running"
  | "completed"
  | "degraded"
  | "failed"
  | "cancelled";

export interface ResponseProgressEvent {
  type: string;
  content?: string;
  metadata?: Record<string, unknown>;
}

export interface ResponseProgressState {
  visible: boolean;
  status: ResponseProgressStatus;
  currentEvent: string;
  label: string;
  completedSteps: number;
  totalSteps: number;
  canRetry: boolean;
}

const ORDER = [
  "run.accepted",
  "intent.resolved",
  "context.loaded",
  "retrieval.started",
  "retrieval.completed",
  "answer.composing",
  "answer.core",
  "run.completed",
];

const TERMINAL: Record<string, ResponseProgressStatus> = {
  "run.completed": "completed",
  "run.degraded": "degraded",
  "run.failed": "failed",
  "run.cancelled": "cancelled",
};

export function buildResponseProgress(
  events: ResponseProgressEvent[],
  isStreaming: boolean,
): ResponseProgressState {
  const teachingEvents = events.filter((event) =>
    String(event.metadata?.teaching_event ?? "").trim(),
  );
  if (teachingEvents.length === 0) {
    return {
      visible: false,
      status: "idle",
      currentEvent: "",
      label: "",
      completedSteps: 0,
      totalSteps: ORDER.length,
      canRetry: false,
    };
  }
  const latest = teachingEvents[teachingEvents.length - 1];
  const currentEvent = String(latest.metadata?.teaching_event ?? "");
  const terminalStatus = TERMINAL[currentEvent];
  const status = terminalStatus ?? (isStreaming ? "running" : "degraded");
  const orderIndex = ORDER.indexOf(currentEvent);
  const completedSteps = terminalStatus
    ? ORDER.length
    : Math.max(0, orderIndex < 0 ? teachingEvents.length - 1 : orderIndex);
  return {
    visible: true,
    status,
    currentEvent,
    label: latest.content || "正在处理",
    completedSteps,
    totalSteps: ORDER.length,
    canRetry: Boolean(latest.metadata?.retryable),
  };
}
