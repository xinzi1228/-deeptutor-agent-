import { apiFetch, apiUrl } from "@/lib/api";
import type { CurrentLearningTask } from "@/lib/current-learning-task-api";
import type {
  ForesightStats,
  LearningReport,
  ProfileOverview,
} from "@/lib/learning-stats-api";

export type StudentDashboardVersion = {
  profile_id: string;
  profile_data_version: number;
  learning_data_version: string;
  task_version: number;
};

export type StudentHomeDashboard = {
  task: CurrentLearningTask | null;
  overview: ProfileOverview;
  report: LearningReport;
  version: StudentDashboardVersion;
  generated_at: string;
};

export type StudentGrowthDashboard = {
  overview: ProfileOverview;
  report: LearningReport;
  foresight: ForesightStats;
  version: StudentDashboardVersion;
  generated_at: string;
};

type Entry<T> = { expiresAt: number; promise: Promise<T> };
const homeRequests = new Map<string, Entry<StudentHomeDashboard>>();
const growthRequests = new Map<string, Entry<StudentGrowthDashboard>>();
const CACHE_MS = 5_000;

function withCallerAbort<T>(promise: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return promise;
  if (signal.aborted) return Promise.reject(new DOMException("Aborted", "AbortError"));
  return new Promise<T>((resolve, reject) => {
    const abort = () => reject(new DOMException("Aborted", "AbortError"));
    const cleanup = () => signal.removeEventListener("abort", abort);
    signal.addEventListener("abort", abort, { once: true });
    promise.then(
      (value) => {
        cleanup();
        resolve(value);
      },
      (error) => {
        cleanup();
        reject(error);
      },
    );
  });
}

function coalesced<T>(
  entries: Map<string, Entry<T>>,
  profileId: string,
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const now = Date.now();
  let entry = entries.get(profileId);
  if (!entry || entry.expiresAt <= now) {
    const promise = apiFetch(apiUrl(path), { cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error(`学生首屏读取失败：${response.status}`);
      const payload = (await response.json()) as T & { version?: StudentDashboardVersion };
      if (payload.version?.profile_id !== profileId) throw new Error("学习档案响应不匹配");
      return payload;
    });
    entry = { expiresAt: now + CACHE_MS, promise };
    entries.set(profileId, entry);
    promise.catch(() => {
      if (entries.get(profileId)?.promise === promise) entries.delete(profileId);
    });
  }
  return withCallerAbort(entry.promise, signal);
}

export function getStudentHomeDashboard(profileId: string, signal?: AbortSignal) {
  return coalesced(homeRequests, profileId, "/api/v1/student-dashboard/home", signal);
}

export function getStudentGrowthDashboard(profileId: string, signal?: AbortSignal) {
  return coalesced(growthRequests, profileId, "/api/v1/student-dashboard/growth", signal);
}

export function invalidateStudentDashboard(profileId?: string): void {
  if (profileId) {
    homeRequests.delete(profileId);
    growthRequests.delete(profileId);
    return;
  }
  homeRequests.clear();
  growthRequests.clear();
}
