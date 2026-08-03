import { apiFetch, apiUrl } from "@/lib/api";

export type StandardSection = string;

export type StandardDoc = {
  id: string;
  title: string;
  sections: string[];
  content: string;
};

export async function getStandards(): Promise<{ standards: StandardDoc[] }> {
  const res = await apiFetch(apiUrl("/api/v1/standards"));
  if (!res.ok) throw new Error(`Failed to load standards: ${res.status}`);
  return res.json();
}
