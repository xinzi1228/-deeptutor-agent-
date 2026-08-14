import { apiFetch, apiUrl } from "@/lib/api";

export type AnnotationMode = "image" | "text" | "audio" | "video" | "pro";
export type AnnotationEditorMode = "teaching" | "professional";

export type AnnotationTaskSummary = {
  id: string;
  modal: "image" | "text" | "audio" | "video";
};

export type AnnotationEditLease = {
  task_id: string;
  mode: AnnotationEditorMode;
  browser_session_id: string;
  version: number;
  checkpoint_version: number;
  expires_at: string;
};

const SESSION_KEY = "annotation-edit-browser-session-v1";

export function getAnnotationBrowserSessionId(): string {
  if (typeof window === "undefined") return "server-session-placeholder";
  const existing = window.sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const created = globalThis.crypto?.randomUUID?.() || `browser-${Date.now()}-${Math.random()}`;
  window.sessionStorage.setItem(SESSION_KEY, created);
  return created;
}

export function isTaskCompatibleWithMode(
  task: AnnotationTaskSummary | undefined,
  mode: AnnotationMode,
): boolean {
  if (!task) return false;
  return mode === "pro" || task.modal === mode;
}

export function chooseCompatibleTask(
  tasks: AnnotationTaskSummary[],
  mode: AnnotationMode,
  selectedTaskId: string,
): string {
  const selected = tasks.find((task) => task.id === selectedTaskId);
  return isTaskCompatibleWithMode(selected, mode) ? selectedTaskId : "";
}

async function leaseRequest(taskId: string, body: Record<string, unknown>) {
  const response = await apiFetch(
    apiUrl(`/api/v1/annotation/edit-leases/${encodeURIComponent(taskId)}`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail;
    const error = new Error(
      typeof detail === "string" ? detail : detail?.message || "无法取得任务编辑权",
    ) as Error & { status?: number; lease?: AnnotationEditLease };
    error.status = response.status;
    error.lease = detail?.lease;
    throw error;
  }
  return data.lease as AnnotationEditLease;
}

export function acquireAnnotationEditLease(
  taskId: string,
  mode: AnnotationEditorMode,
  browserSessionId: string,
) {
  return leaseRequest(taskId, {
    mode,
    browser_session_id: browserSessionId,
  });
}
export function takeoverAnnotationEditLease(
  taskId: string,
  mode: AnnotationEditorMode,
  browserSessionId: string,
  current: AnnotationEditLease,
) {
  return leaseRequest(taskId, {
    mode,
    browser_session_id: browserSessionId,
    takeover: true,
    expected_version: current.version,
    saved_draft_version: current.checkpoint_version,
  });
}

export async function checkpointProfessionalEditLease(
  taskId: string,
  browserSessionId: string,
  current: AnnotationEditLease,
) {
  const response = await apiFetch(
    apiUrl(`/api/v1/annotation/edit-leases/${encodeURIComponent(taskId)}/checkpoint`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "professional",
        browser_session_id: browserSessionId,
        expected_version: current.version,
        draft_version: Date.now(),
      }),
    },
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail || "专业模式保存检查点失败");
  return data.lease as AnnotationEditLease;
}

export async function releaseAnnotationEditLease(
  taskId: string,
  browserSessionId: string,
  current: AnnotationEditLease,
) {
  await apiFetch(apiUrl(`/api/v1/annotation/edit-leases/${encodeURIComponent(taskId)}`), {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      browser_session_id: browserSessionId,
      expected_version: current.version,
    }),
  });
}
