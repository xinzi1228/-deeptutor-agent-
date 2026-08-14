import { apiUrl, apiFetch } from "./api";

export interface ModuleInit {
  id: string;
  name: string;
  order: number;
  pass_threshold?: number;
  knowledge_points: {
    id: string;
    name: string;
    type: string;
    module_id: string;
  }[];
}

export interface LearningKnowledgePoint {
  id: string;
  name: string;
  type: string;
}

export interface LearningModule {
  id: string;
  name: string;
  order: number;
  pass_threshold: number;
  knowledge_points: LearningKnowledgePoint[];
}

export interface ProgressDetail {
  book_id: string;
  modules: LearningModule[];
  mastery_levels: Record<string, number>;
  current_module_id?: string;
  current_stage?: string;
  diagnostic?: unknown;
}

export async function fetchProgress(bookId: string): Promise<ProgressDetail> {
  const res = await apiFetch(apiUrl(`/api/v1/learning/progress/${bookId}`));
  if (!res.ok) throw new Error(`Failed to fetch progress: ${res.status}`);
  return res.json() as Promise<ProgressDetail>;
}

export async function initModules(bookId: string, modules: ModuleInit[]) {
  const res = await apiFetch(
    apiUrl(`/api/v1/learning/progress/${bookId}/init-modules`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modules }),
    },
  );
  if (!res.ok) throw new Error(`Failed to init modules: ${res.status}`);
  return res.json();
}

// ── Mastery map (the dashboard view) ──────────────────────────────────────
// Mirrors deeptutor/learning/policy.py map_summary + next_objective.

export type ObjectiveStatus = "new" | "learning" | "mastered";

export interface MapKnowledgePoint {
  id: string;
  name: string;
  type: string;
  status: ObjectiveStatus;
  mastery: number;
}

export interface MapModule {
  id: string;
  name: string;
  order: number;
  mastered: number;
  total: number;
  knowledge_points: MapKnowledgePoint[];
}

export interface MasteryMap {
  counts: { mastered: number; learning: number; new: number; total: number };
  due_reviews: number;
  complete: boolean;
  modules: MapModule[];
}

export interface NextStep {
  action: string;
  knowledge_point_name: string;
  knowledge_point_type: string;
  status: string;
  mastery: number;
  threshold: number;
  reason: string;
}

export interface MasteryMapResult {
  book_id: string;
  next: NextStep;
  map: MasteryMap;
}

export async function fetchMasteryMap(
  pathId: string,
): Promise<MasteryMapResult> {
  const res = await apiFetch(
    apiUrl(`/api/v1/learning/progress/${encodeURIComponent(pathId)}/map`),
  );
  if (!res.ok) throw new Error(`Failed to fetch mastery map: ${res.status}`);
  return res.json() as Promise<MasteryMapResult>;
}

export interface ProgressSummary {
  book_id: string;
  name: string;
  modules_count: number;
  kp_count: number;
  current_stage: string;
  avg_mastery_pct: number;
  updated_at: number;
}

export interface ProgressListResult {
  summaries: ProgressSummary[];
  errors: { book_id: string; error: string }[];
}

export async function fetchAllProgress(): Promise<ProgressListResult> {
  const res = await apiFetch(apiUrl("/api/v1/learning/progress"));
  if (!res.ok) throw new Error(`Failed to fetch all progress: ${res.status}`);
  return res.json();
}

export async function deleteProgress(bookId: string) {
  const res = await apiFetch(
    apiUrl(`/api/v1/learning/progress/${encodeURIComponent(bookId)}`),
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`Failed to delete progress: ${res.status}`);
  return res.json();
}

export async function redoProgress(bookId: string) {
  const res = await apiFetch(
    apiUrl(`/api/v1/learning/progress/${encodeURIComponent(bookId)}/redo`),
    { method: "POST" },
  );
  if (!res.ok) throw new Error(`Failed to redo progress: ${res.status}`);
  return res.json();
}

export async function importFromBook(
  bookId: string,
  chapters: { title: string; knowledge_points: string[] }[],
) {
  const res = await apiFetch(
    apiUrl(
      `/api/v1/learning/progress/${encodeURIComponent(bookId)}/import-from-book`,
    ),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapters }),
    },
  );
  if (!res.ok) throw new Error(`Failed to import from book: ${res.status}`);
  return res.json();
}

export async function generateModulesFromNotebook(
  bookId: string,
  notebookId: string,
  records: { id: string; type: string; title: string; output: string }[],
): Promise<{ modules: ModuleInit[] }> {
  const res = await apiFetch(
    apiUrl(
      `/api/v1/learning/progress/${encodeURIComponent(bookId)}/generate-from-notebook`,
    ),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notebook_id: notebookId, records }),
    },
  );
  if (!res.ok)
    throw new Error(`Failed to generate modules from notebook: ${res.status}`);
  return res.json();
}

export type BrowserAnnotationDraft = {
  profileId: string;
  taskId: string;
  predictions: Array<Record<string, unknown>>;
  updatedAt: number;
};

export type AnnotationSubmitResult = {
  finalized: boolean;
  sync_status: "synced" | "retry_pending";
  detail?: string;
  attempt?: { task_id: string; metrics?: Record<string, unknown>; report?: string; revision?: Record<string, unknown> };
  grade?: { metrics?: Record<string, unknown>; report?: string };
  local_check?: { metrics?: Record<string, unknown>; report?: string };
  score_record?: AnnotationScoreRecord | null;
};

export type AnnotationScoreRecord = {
  revision_number?: number;
  correction_of?: string;
  metric_delta?: Record<string, number>;
  rule_version?: string;
  reference_version?: string;
  score_hash?: string;
};

const annotationDraftKey = (profileId: string, taskId: string) =>
  `annotation-browser-draft:v1:${profileId}:${taskId}`;

export function saveBrowserAnnotationDraft(draft: BrowserAnnotationDraft): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(annotationDraftKey(draft.profileId, draft.taskId), JSON.stringify(draft));
}

export function readBrowserAnnotationDraft(profileId: string, taskId: string): BrowserAnnotationDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const value = JSON.parse(window.sessionStorage.getItem(annotationDraftKey(profileId, taskId)) || "null");
    return value?.profileId === profileId && value?.taskId === taskId && Array.isArray(value?.predictions) ? value : null;
  } catch {
    return null;
  }
}

export function clearBrowserAnnotationDraft(profileId: string, taskId: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(annotationDraftKey(profileId, taskId));
}

export async function submitAnnotationRevision(body: Record<string, unknown>): Promise<AnnotationSubmitResult> {
  const response = await apiFetch(apiUrl("/api/v1/annotation/attempts"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail || "提交失败");
  return data as AnnotationSubmitResult;
}

export async function retryPendingAnnotationRevisions(): Promise<{
  completed: Array<{ attempt: AnnotationSubmitResult["attempt"]; score_record?: AnnotationScoreRecord | null }>;
  pending: Array<Record<string, unknown>>;
}> {
  const response = await apiFetch(apiUrl("/api/v1/annotation/attempts/retry-pending"), { method: "POST" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail || "同步重试失败");
  return data;
}
