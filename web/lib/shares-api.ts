import { apiFetch, apiUrl } from "@/lib/api";

export type ShareEntry = {
  token: string;
  url: string;
  session_id: string;
};

export async function createShare(sessionId: string): Promise<ShareEntry> {
  const res = await apiFetch(apiUrl("/api/v1/shares"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`Failed to create share: ${res.status}`);
  return res.json();
}

export async function revokeShare(token: string): Promise<{ ok: boolean }> {
  const res = await apiFetch(apiUrl(`/api/v1/shares/${token}`), {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to revoke share: ${res.status}`);
  return res.json();
}
