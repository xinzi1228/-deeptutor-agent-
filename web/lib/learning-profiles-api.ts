import { apiFetch, apiUrl } from "@/lib/api";

export type LearningProfile = {
  id: string;
  owner_user_id: string;
  name: string;
  avatar: string;
  created_at: string;
  updated_at: string;
  failed_attempts: number;
  locked_until: string;
  disabled: boolean;
  data_version: number;
};

export type ActiveLearningProfile = {
  unlocked: boolean;
  profile: LearningProfile | null;
  mode?: "student" | "teacher_view" | "impersonate";
  read_only?: boolean;
};

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : body.detail?.message;
    throw new Error(detail || "学习档案操作失败");
  }
  return response.json() as Promise<T>;
}

export async function listLearningProfiles(): Promise<{ profiles: LearningProfile[]; active_profile_id: string | null }> {
  return json(await apiFetch(apiUrl("/api/v1/learning-profiles")));
}

export async function getActiveLearningProfile(): Promise<ActiveLearningProfile> {
  return json(await apiFetch(apiUrl("/api/v1/learning-profiles/active")));
}

export async function createLearningProfile(input: { name: string; pin: string; avatar?: string }): Promise<LearningProfile> {
  return json(await apiFetch(apiUrl("/api/v1/learning-profiles"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) }));
}

export async function unlockLearningProfile(profileId: string, pin: string): Promise<{ ok: true; profile: LearningProfile }> {
  return json(await apiFetch(apiUrl(`/api/v1/learning-profiles/${profileId}/unlock`), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pin }), skipAuthRedirect: true }));
}

export async function lockLearningProfile(): Promise<void> {
  await json(await apiFetch(apiUrl("/api/v1/learning-profiles/lock"), { method: "POST" }));
}
