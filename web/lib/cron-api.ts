import { apiFetch, apiUrl } from "@/lib/api";

export type CronSchedule = {
  kind: string;
  every_seconds?: number | null;
  at_ms?: number | null;
  expr?: string | null;
  tz?: string | null;
};

export type CronJob = {
  id: string;
  name: string;
  message: string;
  schedule: CronSchedule;
  enabled: boolean;
  next_run_at_ms?: number | null;
  last_status?: string | null;
  last_error?: string | null;
};

export async function getCronJobs(): Promise<{ jobs: CronJob[] }> {
  const res = await apiFetch(apiUrl("/api/v1/cron/jobs"));
  if (!res.ok) throw new Error(`Failed to load cron jobs: ${res.status}`);
  return res.json();
}

export async function deleteCronJob(id: string): Promise<{ ok: boolean }> {
  const res = await apiFetch(apiUrl(`/api/v1/cron/jobs/${id}`), {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete cron job: ${res.status}`);
  return res.json();
}

export async function toggleCronJob(
  id: string,
  enabled: boolean,
): Promise<{ ok: boolean }> {
  const res = await apiFetch(apiUrl(`/api/v1/cron/jobs/${id}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error(`Failed to toggle cron job: ${res.status}`);
  return res.json();
}
