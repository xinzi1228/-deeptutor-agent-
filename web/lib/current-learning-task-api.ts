import { apiFetch, apiUrl } from "@/lib/api";

export type CurrentLearningTask = {
  profile_id: string;
  course_id: string;
  task_id: string;
  phase: "assigned" | "diagnosing" | "theory" | "practice" | "review" | "paused" | "completed";
  mode: "learning" | "teaching_annotation" | "professional_annotation";
  draft_ref: string;
  latest_submission_ref: string;
  coach_session_id: string;
  version: number;
  updated_at: string;
};

export async function fetchCurrentLearningTask(signal?: AbortSignal) {
  const response = await apiFetch(apiUrl("/api/v1/current-learning-task"), {
    cache: "no-store",
    signal,
  });
  if (!response.ok) throw new Error("当前学习任务读取失败");
  return (await response.json()) as { task: CurrentLearningTask | null };
}

export async function openCurrentLearningTask(
  input: {
    courseId: string;
    taskId: string;
    mode: CurrentLearningTask["mode"];
    expectedVersion: number;
  },
  signal?: AbortSignal,
) {
  const response = await apiFetch(apiUrl("/api/v1/current-learning-task"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      course_id: input.courseId,
      task_id: input.taskId,
      phase: "practice",
      mode: input.mode,
      expected_version: input.expectedVersion,
      idempotency_key: `open:${input.courseId}:${input.taskId}:${input.mode}:${input.expectedVersion}`,
    }),
  });
  const payload = (await response.json()) as { task?: CurrentLearningTask; detail?: string };
  if (!response.ok || !payload.task) throw new Error(payload.detail || "当前学习任务更新失败");
  return payload.task;
}
